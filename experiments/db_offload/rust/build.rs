fn main() {
    let path = std::env::var("RELATE_FFI_DIR").expect("RELATE_FFI_DIR must identify pinned Relate 1.0.1 shared library");
    println!("cargo:rustc-link-search=native={path}");
    println!("cargo:rustc-link-lib=dylib=relate_ffi");
    println!("cargo:rerun-if-env-changed=RELATE_FFI_DIR");
}
