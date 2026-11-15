//! Thin access layer over the public `relate` 1.0.1 embedding API.
//!
//! Every statement is parameterized Cypher. Results are converted to JSON maps keyed by
//! column name so the rest of the application never depends on engine value internals.

use std::collections::BTreeMap;
use std::sync::Arc;

use anyhow::{anyhow, Result};
use relate::{Connection, Database, OpenMode, OpenOptions, Value};
use serde_json::{Map, Value as Json};

pub type Row = Map<String, Json>;
pub type Params = BTreeMap<String, Value>;

pub struct Store {
    pub db: Database,
    pub conn: Connection,
    pub read_only: bool,
}

impl Store {
    pub fn open(path: &str, read_only: bool) -> Result<Self> {
        let db = if read_only {
            Database::open_with(path, OpenOptions::with_mode(OpenMode::ReadOnly))
        } else {
            Database::open(path)
        }
        .map_err(|e| anyhow!("open relate store {path}: {e}"))?;
        let conn = db.connect().map_err(|e| anyhow!("connect: {e}"))?;
        Ok(Self {
            db,
            conn,
            read_only,
        })
    }

    pub fn q(&mut self, cypher: &str, params: Params) -> Result<Vec<Row>> {
        let result = self.conn.query_with_params(cypher, params).map_err(|e| {
            anyhow!(
                "{e} [query: {}]",
                cypher.split_whitespace().collect::<Vec<_>>().join(" ")
            )
        })?;
        let cols = result.header.columns.clone();
        Ok(result
            .rows
            .into_iter()
            .map(|row| {
                cols.iter()
                    .cloned()
                    .zip(row.into_iter().map(to_json))
                    .collect()
            })
            .collect())
    }

    pub fn q0(&mut self, cypher: &str) -> Result<Vec<Row>> {
        self.q(cypher, Params::new())
    }

    pub fn begin(&mut self) -> Result<()> {
        self.conn.begin().map_err(|e| anyhow!("begin: {e}"))
    }

    pub fn commit(&mut self) -> Result<Option<String>> {
        self.conn.commit().map_err(|e| anyhow!("commit: {e}"))
    }

    pub fn rollback(&mut self) -> Result<()> {
        self.conn.rollback().map_err(|e| anyhow!("rollback: {e}"))
    }

    /// Run `f` inside one engine transaction; any error rolls the whole write back.
    pub fn tx<T>(&mut self, f: impl FnOnce(&mut Self) -> Result<T>) -> Result<T> {
        self.begin()?;
        match f(self) {
            Ok(v) => {
                self.commit()?;
                Ok(v)
            }
            Err(e) => {
                let _ = self.rollback();
                Err(e)
            }
        }
    }

    pub fn checkpoint(&self) -> Result<()> {
        self.db
            .checkpoint_if_writable()
            .map_err(|e| anyhow!("checkpoint: {e}"))
    }
}

pub fn to_json(v: Value) -> Json {
    match v {
        Value::Null => Json::Null,
        Value::Bool(b) => Json::Bool(b),
        Value::Int(i) => Json::from(i),
        Value::Float(f) => serde_json::Number::from_f64(f)
            .map(Json::Number)
            .unwrap_or(Json::Null),
        Value::String(s) => Json::String(s.to_string()),
        Value::List(l) => Json::Array(l.iter().cloned().map(to_json).collect()),
        Value::Vector { values, .. } => Json::Array(values.iter().cloned().map(to_json).collect()),
        Value::Map(m) => Json::Object(
            m.iter()
                .map(|(k, v)| (k.clone(), to_json(v.clone())))
                .collect(),
        ),
        other => Json::String(format!("{other:?}")),
    }
}

pub fn from_json(v: &Json) -> Value {
    match v {
        Json::Null => Value::Null,
        Json::Bool(b) => Value::Bool(*b),
        Json::Number(n) => n
            .as_i64()
            .map(Value::Int)
            .unwrap_or_else(|| Value::Float(n.as_f64().unwrap_or(0.0))),
        Json::String(s) => Value::String(s.as_str().into()),
        Json::Array(a) => Value::List(Arc::new(a.iter().map(from_json).collect())),
        Json::Object(o) => Value::Map(Arc::new(
            o.iter().map(|(k, v)| (k.clone(), from_json(v))).collect(),
        )),
    }
}

pub fn s(v: impl Into<String>) -> Value {
    Value::String(v.into().as_str().into())
}

pub fn floats(v: &[f32]) -> Value {
    Value::List(Arc::new(
        v.iter().map(|x| Value::Float(*x as f64)).collect(),
    ))
}

pub fn strings<I: IntoIterator<Item = String>>(v: I) -> Value {
    Value::List(Arc::new(
        v.into_iter()
            .map(|x| Value::String(x.as_str().into()))
            .collect(),
    ))
}

#[macro_export]
macro_rules! params {
    ($($k:expr => $v:expr),* $(,)?) => {{
        let mut m = $crate::db::Params::new();
        $( m.insert($k.to_string(), $v); )*
        m
    }};
}

pub fn get_str<'a>(r: &'a Row, k: &str) -> &'a str {
    r.get(k).and_then(|v| v.as_str()).unwrap_or("")
}
