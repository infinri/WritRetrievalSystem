//! Rust inference must reproduce the committed Python-reference embeddings
//! (tests/fixtures/embedding-reference.json) within documented tolerances:
//! cosine >= 0.99999 and max |delta| <= 2e-4 per dimension.
use std::path::PathBuf;
use writ_relate::embed::{cosine, Encoder};

fn model_dir() -> Option<PathBuf> {
    let p =
        PathBuf::from(std::env::var("WRIT_MODEL_DIR").unwrap_or_else(|_| "../data/model".into()));
    p.join("model.onnx").exists().then_some(p)
}

#[test]
fn matches_python_reference_within_tolerance() {
    let Some(dir) = model_dir() else {
        panic!("model not found: set WRIT_MODEL_DIR or run scripts/fetch-model.sh");
    };
    let enc = Encoder::load(&dir).unwrap();
    let fx: serde_json::Value =
        serde_json::from_str(include_str!("fixtures/embedding-reference.json")).unwrap();
    let (mut worst_cos, mut worst_abs) = (1f32, 0f32);
    for case in fx["cases"].as_array().unwrap() {
        let reference: Vec<f32> = case["embedding"]
            .as_array()
            .unwrap()
            .iter()
            .map(|x| x.as_f64().unwrap() as f32)
            .collect();
        let got = enc.embed(case["text"].as_str().unwrap()).unwrap();
        let c = cosine(&got, &reference);
        let a = got
            .iter()
            .zip(&reference)
            .map(|(x, y)| (x - y).abs())
            .fold(0f32, f32::max);
        worst_cos = worst_cos.min(c);
        worst_abs = worst_abs.max(a);
    }
    eprintln!("worst cosine {worst_cos}, worst abs delta {worst_abs}");
    assert!(worst_cos >= 0.99999, "cosine {worst_cos}");
    assert!(worst_abs <= 2e-4, "abs {worst_abs}");
}
