#[cfg(test)]
mod tempdir_tests {
    mod open {
        use std::path::Path;
        use maketemp::TempFile;
        
        #[test]
        fn done() {
            let actfile;
            
            {
                let obj = match TempFile::open() {
                    Ok(v) => { v },
                    Err(msg) => { panic!("{}",msg); }
                };
                actfile = obj.path().to_string();
                
                assert_eq!(true,Path::new(&actfile).exists());
            }
            
            assert_eq!(false,Path::new(&actfile).exists());
        }
    }
    mod open_with {
        use std::path::Path;
        use maketemp::TempFile;
        
        #[test]
        fn give_unauthorized_dir_return_error() {
            let dir = "/root";
            let prefix = "abc-";
            let suffix = ".txt";
            
            {
                match TempFile::open_with(dir,prefix,suffix) {
                    Ok(v) => { panic!("unexpected state. ({})",v.path()); },
                    Err(_msg) => { /* OK! */ }
                }
            }
        }
        #[test]
        fn give_valid_values_return_done() {
            let dir = std::env::current_dir().unwrap();
            let prefix = "abc-";
            let suffix = ".txt";
            let actdir;
            
            {
                let obj = match TempFile::open_with(dir,prefix,suffix) {
                    Ok(v) => { v },
                    Err(msg) => { panic!("{}",msg); }
                };
                actdir = obj.path().to_string();
                
                assert_eq!(true,Path::new(&actdir).exists());
            }
            
            assert_eq!(false,Path::new(&actdir).exists());
        }
    }
}