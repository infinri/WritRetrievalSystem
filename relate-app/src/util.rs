//! Digests, canonical JSON and UTC timestamps (application semantics; the engine has none).

use anyhow::{bail, Result};
use serde_json::Value as Json;
use sha2::{Digest, Sha256};

pub fn sha256_hex(bytes: &[u8]) -> String {
    hex::encode(Sha256::digest(bytes))
}

pub fn text_digest(text: &str) -> String {
    format!("sha256:{}", sha256_hex(text.as_bytes()))
}

/// Canonical JSON: object keys sorted recursively, no insignificant whitespace.
pub fn canonical(v: &Json) -> String {
    fn sort(v: &Json) -> Json {
        match v {
            Json::Object(m) => {
                let mut keys: Vec<_> = m.keys().cloned().collect();
                keys.sort();
                Json::Object(
                    keys.into_iter()
                        .map(|k| (k.clone(), sort(&m[&k])))
                        .collect(),
                )
            }
            Json::Array(a) => Json::Array(a.iter().map(sort).collect()),
            other => other.clone(),
        }
    }
    serde_json::to_string(&sort(v)).expect("serializable")
}

pub fn json_digest(v: &Json) -> String {
    text_digest(&canonical(v))
}

/// Current UTC time as YYYY-MM-DDTHH:MM:SSZ (whole seconds).
pub fn now_utc() -> String {
    let secs = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    format_utc(secs as i64)
}

pub fn format_utc(secs: i64) -> String {
    let days = secs.div_euclid(86_400);
    let rem = secs.rem_euclid(86_400);
    // Howard Hinnant's civil_from_days.
    let z = days + 719_468;
    let era = z.div_euclid(146_097);
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = if m <= 2 { y + 1 } else { y };
    format!(
        "{y:04}-{m:02}-{d:02}T{:02}:{:02}:{:02}Z",
        rem / 3600,
        rem % 3600 / 60,
        rem % 60
    )
}

/// Strict UTC timestamp check; lexical order equals time order for this format.
pub fn check_utc(s: &str) -> Result<()> {
    let b = s.as_bytes();
    let digits = [0, 1, 2, 3, 5, 6, 8, 9, 11, 12, 14, 15, 17, 18];
    let ok = b.len() == 20
        && digits.iter().all(|&i| b[i].is_ascii_digit())
        && b[4] == b'-'
        && b[7] == b'-'
        && b[10] == b'T'
        && b[13] == b':'
        && b[16] == b':'
        && b[19] == b'Z';
    if !ok {
        bail!("time must be UTC YYYY-MM-DDTHH:MM:SSZ: {s}");
    }
    let n = |a: usize, l: usize| s[a..a + l].parse::<u32>().unwrap();
    let (mo, d, h, mi, se) = (n(5, 2), n(8, 2), n(11, 2), n(14, 2), n(17, 2));
    if !(1..=12).contains(&mo) || !(1..=31).contains(&d) || h > 23 || mi > 59 || se > 59 {
        bail!("impossible UTC time: {s}");
    }
    Ok(())
}

/// Lexical query preparation equivalent to the Python reference: lowercase alphanumeric
/// runs of the first 2,000 characters, joined by spaces.
pub fn keywords(text: &str) -> String {
    let head: String = text.chars().take(2000).collect::<String>().to_lowercase();
    head.split(|c: char| !c.is_alphanumeric())
        .filter(|w| !w.is_empty())
        .collect::<Vec<_>>()
        .join(" ")
}

/// Engine identifiers (labels/index names) derived from a project name; never raw user text.
pub fn scope_tag(project: &str) -> String {
    sha256_hex(project.as_bytes())[..12].to_string()
}

pub fn check_project(p: &str) -> Result<()> {
    if p.is_empty()
        || p.len() > 64
        || !p
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || "-_.".contains(c))
    {
        bail!("project must be 1-64 ASCII letters, digits, '-', '_' or '.': {p}");
    }
    Ok(())
}

pub fn check_id(id: &str) -> Result<()> {
    if id.is_empty()
        || id.len() > 128
        || id.contains('|')
        || id.contains('@')
        || id.chars().any(char::is_control)
    {
        bail!("invalid record id: {id:?}");
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn utc_roundtrip() {
        assert_eq!(format_utc(0), "1970-01-01T00:00:00Z");
        assert_eq!(format_utc(1_700_000_000), "2023-11-14T22:13:20Z");
        check_utc("2026-11-14T12:00:00Z").unwrap();
        assert!(check_utc("2026-11-14T12:00:00+00:00").is_err());
        assert!(check_utc("2026-13-14T12:00:00Z").is_err());
    }
    #[test]
    fn keyword_prep() {
        assert_eq!(
            keywords("What is X_y? Façade, 2-hop!"),
            "what is x y façade 2 hop"
        );
    }
}
