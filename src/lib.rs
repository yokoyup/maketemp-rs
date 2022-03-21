//! Create temporary directory and file.
//! 
//! - No dependencies.
//! - Create in any directory.
//! - Add prefix and suffix in the name.
//! - Auto deletion.
//! 
//! ```rust
//! use maketemp::TempDir;
//! use std::path::Path;
//! 
//! fn main() {
//!     let p;
//!     
//!     {
//!         // create temporary directory.
//!         let dir = TempDir::open();
//!         p = dir.path().to_string();
//!         
//!         // true.
//!         println!("path {} exists: {} ",&p,Path::new(&p).exists());
//!         
//!         // delete `dir` automatically here.
//!     }
//!     
//!     // false.
//!     println!("path: {} exists: {}",&p,Path::new(&p).exists());
//! }
//! ```

use std::{
    path::Path,
    time::{ Duration,SystemTime,UNIX_EPOCH }
};

fn make_path<P:AsRef<Path>,N1:AsRef<str>,N2:AsRef<str>>(dir:P,prefix:N1,suffix:N2) -> std::path::PathBuf {
    loop {
        let now = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_micros();
        let p = dir.as_ref().join(format!("{}{}{}",prefix.as_ref(),now,suffix.as_ref()));
        if !p.exists() { return p; }
        std::thread::sleep(Duration::from_micros(1));
    };
}

/// Temporary Directory.
pub struct TempDir {
    path:String
}

impl TempDir {
    /// Create temporary directory in user temporary directory.
    pub fn open() -> Result<Self,String> {
        let tmpdir = std::env::temp_dir();
        
        let path = make_path(tmpdir,"temp-","");
        match std::fs::create_dir(&path) {
            Ok(()) => {
                Ok(Self { path:path.as_os_str().to_str().unwrap().to_string() })
            },
            Err(err) => { Err(format!("{}",err)) }
        }
    }
    /// Create temporary directory in the given directory.
    /// 
    /// - `dir`    - directory path to create.
    /// - `prefix` - prefix name.
    pub fn open_with<P:AsRef<Path>,N:AsRef<str>>(dir:P,prefix:N) -> Result<Self,String> {
        let path = make_path(dir,prefix,"");
        match std::fs::create_dir(&path) {
            Ok(()) => {
                Ok(Self { path:path.as_os_str().to_str().unwrap().to_string() })
            },
            Err(err) => { Err(format!("{}",err)) }
        }
    }
    /// Return directory path.
    pub fn path(&self) -> &str {
        self.path.as_str()
    }
}

impl Drop for TempDir {
    fn drop(&mut self) {
        let p = Path::new(&self.path);
        if p.exists() {
            std::fs::remove_dir_all(p).unwrap();
        }
    }
}

/// Temporary File.
pub struct TempFile {
    path:String
}

impl TempFile {
    /// Create temporary file in user temporary directory.
    pub fn open() -> Result<Self,String> {
        let tmpdir = std::env::temp_dir();
        
        let path = make_path(tmpdir,"","");
        {
            let _f = match std::fs::OpenOptions::new().create_new(true).write(true).open(&path) {
                Ok(v) => { v },
                Err(err) => { return Err(format!("{}",err)); },
            };
        }
        Ok(Self { path:path.as_os_str().to_str().unwrap().to_string() })
    }
    /// Create temporary file in the given directory.
    /// 
    /// - `dir`    - directory path to create.
    /// - `suffix` - suffix name.
    pub fn open_with<P:AsRef<Path>,N1:AsRef<str>,N2:AsRef<str>>(dir:P,prefix:N1,suffix:N2) -> Result<Self,String> {
        let path = make_path(dir,prefix,suffix);
        {
            let _f = match std::fs::OpenOptions::new().create_new(true).write(true).open(&path) {
                Ok(v) => { v },
                Err(err) => { return Err(format!("{}",err)); },
            };
        }
        Ok(Self { path:path.as_os_str().to_str().unwrap().to_string() })
    }
    /// Return directory path.
    pub fn path(&self) -> &str {
        self.path.as_str()
    }
}

impl Drop for TempFile {
    fn drop(&mut self) {
        let p = Path::new(&self.path);
        if p.exists() {
            std::fs::remove_file(&self.path).unwrap();
        }
    }
}