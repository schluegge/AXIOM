use std::path::Path;

pub const DOCUMENT_KIND: &str = "axiom.mvp-contract";
pub const SCHEMA_VERSION: &str = "0.1.0";
pub const SOURCE_VERSION: &str = "0.1.0";
pub const CANONICAL_CONTRACT: &str = include_str!("../../../contracts/mvp.json");

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ContractIdentity {
    pub document_kind: &'static str,
    pub schema_version: &'static str,
    pub source_version: &'static str,
}

pub const fn canonical_identity() -> ContractIdentity {
    ContractIdentity {
        document_kind: DOCUMENT_KIND,
        schema_version: SCHEMA_VERSION,
        source_version: SOURCE_VERSION,
    }
}

pub fn canonical_contract_path(repository_root: &Path) -> std::path::PathBuf {
    repository_root.join("contracts").join("mvp.json")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn embedded_contract_has_frozen_identity() {
        assert!(CANONICAL_CONTRACT.contains(r#"document_kind": "axiom.mvp-contract"#));
        assert!(CANONICAL_CONTRACT.contains(r#"schema_version": "0.1.0"#));
        assert_eq!(canonical_identity().source_version, "0.1.0");
    }
}
