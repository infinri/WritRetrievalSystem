//! The Rust extractor must reproduce the committed passage fixtures exactly from the public
//! Writ Git objects. Requires a local clone: set WRIT_PUBLIC_REPO (CI clones it).
use std::path::PathBuf;
use writ_relate::extract::extract;

#[test]
fn extractor_reproduces_committed_fixtures() {
    let Ok(repo) = std::env::var("WRIT_PUBLIC_REPO") else {
        eprintln!("WRIT_PUBLIC_REPO not set; skipping (CI runs this)");
        return;
    };
    for rev in [
        "a0e0e413e3b20082a85e7d75c58b45b0ba09b903",
        "b60bf33983b96ccfbc5c1464dcf32687c789703e",
    ] {
        let fx: serde_json::Value = serde_json::from_str(
            &std::fs::read_to_string(format!(
                "../experiments/reliable_memory/fixtures/history-{}.json",
                &rev[..7]
            ))
            .unwrap(),
        )
        .unwrap();
        let mut paths: Vec<String> = vec![];
        for d in fx["documents"].as_array().unwrap() {
            let p = d["path"].as_str().unwrap().to_string();
            if !paths.contains(&p) {
                paths.push(p);
            }
        }
        let got = extract(
            &PathBuf::from(&repo),
            rev,
            &paths,
            "https://github.com/infinri/Writ",
            "MIT License",
        )
        .unwrap();
        let expected: Vec<serde_json::Value> = fx["documents"]
            .as_array()
            .unwrap()
            .iter()
            .map(|d| {
                let mut d = d.clone();
                d.as_object_mut().unwrap().remove("file_group");
                d
            })
            .collect();
        assert_eq!(
            got["documents"].as_array().unwrap(),
            &expected,
            "revision {rev}"
        );
        assert_eq!(got["recorded_at"], fx["recorded_at"]);
    }
}
