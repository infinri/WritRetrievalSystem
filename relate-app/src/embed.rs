//! Sentence embeddings for search, computed in-process with the pinned public MiniLM ONNX
//! model (sentence-transformers/all-MiniLM-L6-v2 @ 1110a243) through tract (pure Rust) and
//! the HuggingFace `tokenizers` crate. Same preparation as the historical Python encoder:
//! 128-token truncation, fixed padding, attention-mask mean pooling, L2 normalization.
//! This is embedding inference only; it is not a learned reranker.

use std::path::Path;

use anyhow::{anyhow, bail, Context, Result};
use sha2::{Digest, Sha256};
use tokenizers::{PaddingParams, PaddingStrategy, Tokenizer, TruncationParams};
use tract_onnx::prelude::*;

pub const MAX_TOKENS: usize = 128;
pub const DIMS: usize = 384;
pub const TEXT_HEAD_CHARS: usize = 1600;
pub const MODEL_SHA256: &str = "6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452";
pub const TOKENIZER_SHA256: &str =
    "be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037";

type Plan = SimplePlan<TypedFact, Box<dyn TypedOp>, Graph<TypedFact, Box<dyn TypedOp>>>;

pub struct Encoder {
    tokenizer: Tokenizer,
    plan: Plan,
    input_order: Vec<String>,
    pub identity: String,
}

fn sha256_file(p: &Path) -> Result<String> {
    Ok(hex::encode(Sha256::digest(
        std::fs::read(p).with_context(|| format!("read {}", p.display()))?,
    )))
}

impl Encoder {
    pub fn load(dir: &Path) -> Result<Self> {
        let (model, tok) = (dir.join("model.onnx"), dir.join("tokenizer.json"));
        let (m, t) = (sha256_file(&model)?, sha256_file(&tok)?);
        if m != MODEL_SHA256 || t != TOKENIZER_SHA256 {
            bail!("model artifacts do not match the pinned hashes (model {m}, tokenizer {t}); run scripts/fetch-model.sh");
        }
        let mut tokenizer = Tokenizer::from_file(&tok).map_err(|e| anyhow!("tokenizer: {e}"))?;
        tokenizer
            .with_truncation(Some(TruncationParams {
                max_length: MAX_TOKENS,
                ..Default::default()
            }))
            .map_err(|e| anyhow!("truncation: {e}"))?;
        tokenizer.with_padding(Some(PaddingParams {
            strategy: PaddingStrategy::Fixed(MAX_TOKENS),
            ..Default::default()
        }));
        let mut graph = tract_onnx::onnx().model_for_path(&model)?;
        let input_order: Vec<String> = graph
            .input_outlets()?
            .iter()
            .map(|o| graph.node(o.node).name.clone())
            .collect();
        for i in 0..input_order.len() {
            graph.set_input_fact(i, i64::fact([1, MAX_TOKENS]).into())?;
        }
        let plan = graph.into_optimized()?.into_runnable()?;
        let identity = format!(
            "sha256:{}",
            hex::encode(Sha256::digest(
                format!("minilm-l6-v2|{m}|{t}|{MAX_TOKENS}|mean|l2|tract").as_bytes()
            ))
        );
        Ok(Self {
            tokenizer,
            plan,
            input_order,
            identity,
        })
    }

    pub fn embed(&self, text: &str) -> Result<Vec<f32>> {
        let enc = self
            .tokenizer
            .encode(text, true)
            .map_err(|e| anyhow!("tokenize: {e}"))?;
        let mask: Vec<i64> = enc.get_attention_mask().iter().map(|&x| x as i64).collect();
        let pick = |name: &str| -> Vec<i64> {
            match name {
                "input_ids" => enc.get_ids().iter().map(|&x| x as i64).collect(),
                "attention_mask" => mask.clone(),
                _ => enc.get_type_ids().iter().map(|&x| x as i64).collect(),
            }
        };
        let inputs: TVec<TValue> = self
            .input_order
            .iter()
            .map(|n| {
                Ok(
                    tract_ndarray::Array2::from_shape_vec((1, MAX_TOKENS), pick(n))?
                        .into_tensor()
                        .into(),
                )
            })
            .collect::<Result<_>>()?;
        let out = self.plan.run(inputs)?;
        let hidden = out[0].to_array_view::<f32>()?; // [1, tokens, 384]
        let mut pooled = vec![0f32; DIMS];
        let count: f32 = mask.iter().map(|&m| m as f32).sum::<f32>().max(1e-9);
        for (t, &m) in mask.iter().enumerate() {
            if m == 1 {
                for d in 0..DIMS {
                    pooled[d] += hidden[[0, t, d]];
                }
            }
        }
        pooled.iter_mut().for_each(|x| *x /= count);
        let norm = pooled.iter().map(|x| x * x).sum::<f32>().sqrt().max(1e-12);
        pooled.iter_mut().for_each(|x| *x /= norm);
        Ok(pooled)
    }
}

/// Text preparation shared by import and query: record title and body, first 1,600 chars.
pub fn prepare(title: &str, body: &str) -> String {
    let joined = if title.is_empty() {
        body.to_string()
    } else {
        format!("{title}\n{body}")
    };
    joined.chars().take(TEXT_HEAD_CHARS).collect()
}

pub fn cosine(a: &[f32], b: &[f32]) -> f32 {
    a.iter().zip(b).map(|(x, y)| x * y).sum()
}
