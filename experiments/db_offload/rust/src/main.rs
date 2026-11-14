//! Thin query transport only. The same Python harness retains contracts/model/rendering.
use serde_json::{json,Map,Value};
use std::{ffi::{CStr,CString,c_char,c_void},io::{self,BufRead,Read,Write},net::TcpStream,ptr};
type H=*mut c_void;
#[link(name="relate_ffi")]
extern "C" {
 fn relate_abi_version()->i32;
 fn relate_database_open_read_only(uri:*const c_char,out:*mut H,err:*mut *mut c_char)->i32;
 fn relate_database_close(db:H)->i32;
 fn relate_connect_namespace(db:H,name:*const c_char,out:*mut H,err:*mut *mut c_char)->i32;
 fn relate_disconnect(c:H)->i32;
 fn relate_params_new()->H; fn relate_params_free(p:H);
 fn relate_params_put_null(p:H,n:*const c_char,e:*mut *mut c_char)->i32;
 fn relate_params_put_bool(p:H,n:*const c_char,v:u8,e:*mut *mut c_char)->i32;
 fn relate_params_put_int(p:H,n:*const c_char,v:i64,e:*mut *mut c_char)->i32;
 fn relate_params_put_float(p:H,n:*const c_char,v:f64,e:*mut *mut c_char)->i32;
 fn relate_params_put_string(p:H,n:*const c_char,v:*const c_char,len:usize,e:*mut *mut c_char)->i32;
 fn relate_params_put_list(p:H,n:*const c_char,out:*mut H,e:*mut *mut c_char)->i32;
 fn relate_params_put_map(p:H,n:*const c_char,out:*mut H,e:*mut *mut c_char)->i32;
 fn relate_query_params(c:H,q:*const c_char,p:H,out:*mut H,e:*mut *mut c_char)->i32;
 fn relate_free_string(s:*mut c_char);
 fn relate_result_is_error(r:H)->u8;fn relate_result_error_json(r:H)->*const c_char;
 fn relate_column_count(r:H)->i64;fn relate_row_count(r:H)->i64;fn relate_column_name(r:H,col:i64)->*const c_char;
 fn relate_value_at(r:H,row:i64,col:i64)->H;fn relate_value_kind(v:H)->i32;
 fn relate_value_bool(v:H,out:*mut u8)->i32;fn relate_value_int(v:H,out:*mut i64)->i32;fn relate_value_float(v:H,out:*mut f64)->i32;
 fn relate_value_string(v:H,len:*mut usize)->*const c_char;
 fn relate_value_list_len(v:H)->i64;fn relate_value_list_get(v:H,i:i64)->H;
 fn relate_value_map_len(v:H)->i64;fn relate_value_map_key(v:H,i:i64,len:*mut usize)->*const c_char;fn relate_value_map_get(v:H,k:*const c_char)->H;
 fn relate_destroy_result(r:H);
}
unsafe fn status(s:i32,e:*mut c_char)->Result<(),String>{
 if s==0 {return Ok(())} let text=if e.is_null(){"Relate error without detail".into()}else{CStr::from_ptr(e).to_string_lossy().into_owned()};
 if !e.is_null(){relate_free_string(e)}Err(text)
}
unsafe fn put(p:H,name:Option<&str>,v:&Value)->Result<(),String>{
 let name=name.map(|s|CString::new(s).map_err(|e|e.to_string())).transpose()?;let key=name.as_ref().map_or(ptr::null(),|s|s.as_ptr());let mut e=ptr::null_mut();
 let s=match v{
  Value::Null=>relate_params_put_null(p,key,&mut e), Value::Bool(b)=>relate_params_put_bool(p,key,*b as u8,&mut e),
  Value::Number(n)=>if let Some(i)=n.as_i64(){relate_params_put_int(p,key,i,&mut e)}else{relate_params_put_float(p,key,n.as_f64().ok_or("number range")?,&mut e)},
  Value::String(t)=>relate_params_put_string(p,key,t.as_ptr().cast(),t.len(),&mut e),
  Value::Array(values)=>{let mut child=ptr::null_mut();let s=relate_params_put_list(p,key,&mut child,&mut e);status(s,e)?;for v in values{put(child,None,v)?}return Ok(())},
  Value::Object(values)=>{let mut child=ptr::null_mut();let s=relate_params_put_map(p,key,&mut child,&mut e);status(s,e)?;for(k,v)in values{put(child,Some(k),v)?}return Ok(())}
 };status(s,e)
}
unsafe fn bytes(p:*const c_char,n:usize)->String{String::from_utf8_lossy(std::slice::from_raw_parts(p.cast(),n)).into_owned()}
unsafe fn value(v:H)->Result<Value,String>{Ok(match relate_value_kind(v){
 0=>Value::Null,1=>{let mut b=0;status(relate_value_bool(v,&mut b),ptr::null_mut())?;json!(b!=0)},
 2=>{let mut i=0;status(relate_value_int(v,&mut i),ptr::null_mut())?;json!(i)},
 3=>{let mut f=0.;status(relate_value_float(v,&mut f),ptr::null_mut())?;if !f.is_finite(){return Err("non-finite result".into())}json!(f)},
 4=>{let mut n=0;let p=relate_value_string(v,&mut n);if p.is_null(){return Err("null string".into())}json!(bytes(p,n))},
 8=>Value::Array((0..relate_value_list_len(v)).map(|i|value(relate_value_list_get(v,i))).collect::<Result<Vec<_>,_>>()?),
 9=>{let mut m=Map::new();for i in 0..relate_value_map_len(v){let mut n=0;let key=relate_value_map_key(v,i,&mut n);if key.is_null(){return Err("null map key".into())}let text=bytes(key,n);let c=CString::new(text.clone()).map_err(|e|e.to_string())?;m.insert(text,value(relate_value_map_get(v,c.as_ptr()))?);}Value::Object(m)},
 other=>return Err(format!("unsupported result type {other}; no lossy node reinterpretation"))})}
struct Db{db:H,conn:H}
impl Db{
 unsafe fn open(path:&str)->Result<Self,String>{if relate_abi_version()!=2{return Err("expected Relate ABI 2".into())}let path=CString::new(path).map_err(|e|e.to_string())?;let mut db=ptr::null_mut();let mut conn=ptr::null_mut();let mut e=ptr::null_mut();status(relate_database_open_read_only(path.as_ptr(),&mut db,&mut e),e)?;let s=relate_connect_namespace(db,ptr::null(),&mut conn,&mut e);if let Err(error)=status(s,e){relate_database_close(db);return Err(error)}Ok(Self{db,conn})}
 unsafe fn execute(&self,q:&str,args:&Value)->Result<Value,String>{
  let root=relate_params_new();let outcome=(||{for(k,v)in args.as_object().ok_or("params must be object")?{put(root,Some(k),v)?}let cypher=CString::new(q).map_err(|e|e.to_string())?;let mut result=ptr::null_mut();let mut e=ptr::null_mut();let s=relate_query_params(self.conn,cypher.as_ptr(),root,&mut result,&mut e);status(s,e)?;
   let read=(||{if relate_result_is_error(result)!=0{return Err(CStr::from_ptr(relate_result_error_json(result)).to_string_lossy().into_owned())}let mut rows=Vec::new();for row in 0..relate_row_count(result){let mut map=Map::new();for col in 0..relate_column_count(result){let name=CStr::from_ptr(relate_column_name(result,col)).to_string_lossy().into_owned();map.insert(name,value(relate_value_at(result,row,col))?);}rows.push(Value::Object(map));}Ok(Value::Array(rows))})();relate_destroy_result(result);read
  })();relate_params_free(root);outcome
 }
}
impl Drop for Db{fn drop(&mut self){unsafe{relate_disconnect(self.conn);relate_database_close(self.db);}}}
fn neo(q:&str,params:&Value)->Result<Value,String>{
 let body=json!({"statements":[{"statement":q,"parameters":params}]}).to_string();let mut stream=TcpStream::connect("127.0.0.1:17474").map_err(|e|e.to_string())?;stream.set_read_timeout(Some(std::time::Duration::from_secs(180))).map_err(|e|e.to_string())?;
 let request=format!("POST /db/neo4j/tx/commit HTTP/1.0\r\nHost: 127.0.0.1:17474\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",body.len(),body);stream.write_all(request.as_bytes()).map_err(|e|e.to_string())?;
 let mut raw=Vec::new();stream.read_to_end(&mut raw).map_err(|e|e.to_string())?;let boundary=raw.windows(4).position(|w|w==b"\r\n\r\n").ok_or("bad HTTP response")?;
 let head=String::from_utf8_lossy(&raw[..boundary]);if !head.contains("200"){return Err(head.into_owned())}if head.to_lowercase().contains("transfer-encoding: chunked"){return Err("unexpected chunked HTTP/1.0 response".into())}
 let data:Value=serde_json::from_slice(&raw[boundary+4..]).map_err(|e|e.to_string())?;
 if data["errors"].as_array().map_or(true,|a|!a.is_empty()){return Err(data["errors"].to_string())}
 let result=&data["results"][0];let columns=result["columns"].as_array().ok_or("missing columns")?;let mut rows=Vec::new();for row in result["data"].as_array().ok_or("missing data")?{let mut map=Map::new();for(i,c)in columns.iter().enumerate(){map.insert(c.as_str().ok_or("invalid column")?.into(),row["row"][i].clone());}rows.push(Value::Object(map));}Ok(Value::Array(rows))
}
fn main(){let args:Vec<_>=std::env::args().collect();let backend=args.get(1).map(String::as_str).unwrap_or("");let db=if backend=="relate"{match unsafe{Db::open(args.get(2).expect("store path"))}{Ok(d)=>Some(d),Err(e)=>{eprintln!("{e}");std::process::exit(2)}}}else if backend=="neo4j"{None}else{eprintln!("relate PATH | neo4j");std::process::exit(2)};
 let stdin=io::stdin();for line in stdin.lock().lines(){let result=(||{let line=line.map_err(|e|e.to_string())?;if line.len()>16*1024*1024{return Err("request too large".into())}let request:Value=serde_json::from_str(&line).map_err(|e|e.to_string())?;let q=request["query"].as_str().ok_or("query missing")?;if let Some(ref d)=db{unsafe{d.execute(q,&request["params"])}}else{neo(q,&request["params"])}})();let reply=match result{Ok(rows)=>json!({"rows":rows}),Err(error)=>json!({"error":error})};println!("{reply}");io::stdout().flush().unwrap();}}
