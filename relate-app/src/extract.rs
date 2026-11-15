//! Read-only paragraph extraction from exact Git objects (Rust port of the historical
//! `export_passages`). Uses `git cat-file`/`git show` only: no checkout, fetch, hooks or
//! execution of repository code. Offsets are Unicode codepoints, matching the reference ids.

use std::path::Path;
use std::process::Command;

use anyhow::{bail, Context, Result};
use serde_json::{json, Value as Json};

use crate::util::{format_utc, sha256_hex, text_digest};

fn git(repo: &Path, args: &[&str]) -> Result<Vec<u8>> {
    let out = Command::new("git")
        .arg("-C")
        .arg(repo)
        .args(["-c", "core.hooksPath=/dev/null"])
        .args(args)
        .env("GIT_NO_LAZY_FETCH", "1")
        .output()
        .context("run git")?;
    if !out.status.success() {
        bail!(
            "git {} failed: {}",
            args.join(" "),
            String::from_utf8_lossy(&out.stderr).trim()
        );
    }
    Ok(out.stdout)
}

fn is_ws(c: char) -> bool {
    c.is_whitespace()
}

/// Paragraphs of one Markdown text: under each `## ` heading, blank-line separated runs,
/// 70..=1600 characters, excluding code fences, HTML and tables.
pub fn paragraphs(text: &str) -> Vec<(String, usize, String)> {
    let chars: Vec<char> = text.chars().collect();
    // Level-two headings: (line start, line end, heading text).
    let mut heads = vec![];
    let mut i = 0;
    while i <= chars.len() {
        let end = chars[i..]
            .iter()
            .position(|&c| c == '\n')
            .map(|p| i + p)
            .unwrap_or(chars.len());
        if end - i > 3 && chars[i] == '#' && chars[i + 1] == '#' && chars[i + 2] == ' ' {
            heads.push((i, end, chars[i + 3..end].iter().collect::<String>()));
        }
        if end >= chars.len() {
            break;
        }
        i = end + 1;
    }
    let mut out = vec![];
    for (h, (_, hend, heading)) in heads.iter().enumerate() {
        let sec_end = heads.get(h + 1).map(|x| x.0).unwrap_or(chars.len());
        let sec = &chars[*hend..sec_end];
        let mut p = 0;
        loop {
            let Some(s) = sec[p..].iter().position(|&c| !is_ws(c)).map(|x| p + x) else {
                break;
            };
            // Lazy match up to the first "\n<whitespace>*\n" lookahead or end of section.
            let mut e = sec.len();
            let mut j = s + 1;
            while j < sec.len() {
                if sec[j] == '\n' {
                    // "\n\s*\n": the next newline is reached through whitespace only.
                    let mut kk = j + 1;
                    let mut blank = false;
                    while kk < sec.len() && is_ws(sec[kk]) {
                        if sec[kk] == '\n' {
                            blank = true;
                            break;
                        }
                        kk += 1;
                    }
                    if blank {
                        e = j;
                        break;
                    }
                }
                j += 1;
            }
            let raw: String = sec[s..e].iter().collect();
            let passage = raw.trim_matches(is_ws).to_string();
            let n = passage.chars().count();
            let start = hend + s;
            if (70..=1600).contains(&n)
                && !["~~~", "```", "<", "|"]
                    .iter()
                    .any(|x| passage.starts_with(x))
            {
                out.push((heading.clone(), start, passage));
            }
            p = e;
            if p >= sec.len() {
                break;
            }
        }
    }
    out
}

pub fn extract(
    repo: &Path,
    revision: &str,
    paths: &[String],
    repository_url: &str,
    license_marker: &str,
) -> Result<Json> {
    if revision.len() != 40 || !revision.bytes().all(|b| b.is_ascii_hexdigit()) {
        bail!("exact forty-hex Git revision required");
    }
    if paths.is_empty() || paths.len() > 32 {
        bail!("1..32 distinct source paths required");
    }
    for p in paths {
        if p.starts_with('/')
            || p.split('/').any(|x| x == ".." || x.is_empty())
            || !p.ends_with(".md")
        {
            bail!("normalized repository Markdown path required: {p}");
        }
    }
    let resolved = String::from_utf8(git(
        repo,
        &["rev-parse", "--verify", &format!("{revision}^{{commit}}")],
    )?)?;
    if resolved.trim() != revision {
        bail!("Git revision mismatch");
    }
    let license = String::from_utf8(git(repo, &["show", &format!("{revision}:LICENSE")])?)?;
    if !license.contains(license_marker) {
        bail!("LICENSE at {revision} does not contain {license_marker:?}; refusing to import non-redistributable text");
    }
    let ct: i64 = String::from_utf8(git(repo, &["show", "-s", "--format=%ct", revision])?)?
        .trim()
        .parse()?;
    let recorded_at = format_utc(ct);
    let mut docs = vec![];
    let mut total = 0usize;
    for path in paths {
        let text = String::from_utf8(git(
            repo,
            &["cat-file", "-p", &format!("{revision}:{path}")],
        )?)?;
        total += text.len();
        if total > 8_000_000 {
            bail!("source bytes exceed 8 MB limit");
        }
        let src = sha256_hex(text.as_bytes());
        let chars: Vec<char> = text.chars().collect();
        for (heading, start, passage) in paragraphs(&text) {
            let end = start + passage.chars().count();
            let line = |k: usize| chars[..k].iter().filter(|&&c| c == '\n').count() + 1;
            let id = &sha256_hex(format!("{path}\0{start}\0{passage}").as_bytes())[..24];
            docs.push(json!({"id": id, "path": path, "heading": heading, "text": passage, "start": start, "end": end,
                "start_line": line(start), "end_line": line(end), "revision": revision, "committed_at": recorded_at,
                "source_digest": src, "content_digest": text_digest(&passage),
                "uri": format!("{repository_url}/blob/{revision}/{path}#L{}", line(start))}));
            if docs.len() > 1000 {
                bail!("source passage count exceeds 1000");
            }
        }
    }
    Ok(
        json!({"contract_version": "writ-passage-fixture/1", "repository": repository_url, "revision": revision,
        "license": format!("{license_marker} (LICENSE at {revision})"), "recorded_at": recorded_at, "documents": docs}),
    )
}
