//! Offline boundary for read-only agent surfaces (context, inspect, verify, mcp).
//!
//! Rust equivalent of the historical `deny_network()`: on Linux a seccomp filter makes
//! `socket(AF_INET | AF_INET6, ...)` fail with EACCES for every thread of the process.
//! Unix-domain sockets and files are unaffected. This is a network boundary, not an
//! execution-control framework. On other platforms the call reports `unsupported`.

#[cfg(target_os = "linux")]
pub fn deny_network() -> anyhow::Result<&'static str> {
    use seccompiler::{
        SeccompAction, SeccompCmpArgLen, SeccompCmpOp, SeccompCondition, SeccompFilter,
        SeccompRule, TargetArch,
    };
    use std::collections::BTreeMap;
    let arch = match std::env::consts::ARCH {
        "x86_64" => TargetArch::x86_64,
        "aarch64" => TargetArch::aarch64,
        other => anyhow::bail!("seccomp network deny unsupported on {other}"),
    };
    let domain = |af: i32| -> anyhow::Result<SeccompRule> {
        Ok(SeccompRule::new(vec![SeccompCondition::new(
            0,
            SeccompCmpArgLen::Dword,
            SeccompCmpOp::Eq,
            af as u64,
        )?])?)
    };
    let mut rules = BTreeMap::new();
    rules.insert(
        libc::SYS_socket,
        vec![domain(libc::AF_INET)?, domain(libc::AF_INET6)?],
    );
    let filter = SeccompFilter::new(
        rules,
        SeccompAction::Allow,
        SeccompAction::Errno(libc::EACCES as u32),
        arch,
    )?;
    let program: seccompiler::BpfProgram = filter.try_into()?;
    // SAFETY: plain prctl call; required before an unprivileged seccomp filter.
    if unsafe { libc::prctl(libc::PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) } != 0 {
        anyhow::bail!("PR_SET_NO_NEW_PRIVS failed");
    }
    seccompiler::apply_filter_all_threads(&program)?;
    Ok("seccomp: AF_INET/AF_INET6 sockets denied")
}

#[cfg(not(target_os = "linux"))]
pub fn deny_network() -> anyhow::Result<&'static str> {
    Ok("unsupported on this platform: no network deny installed")
}
