#[cfg(test)]
mod tempdir_tests {
    mod open {
        use std::path::Path;
        use maketemp::TempDir;
        
        #[test]
        fn done() {
            let actdir;
            
            {
                let obj = match TempDir::open() {
                    Ok(v) => { v },
                    Err(msg) => { panic!("{}",msg); }
                };
                actdir = obj.path().to_string();
                
                assert_eq!(true,Path::new(&actdir).exists());
            }
            
            assert_eq!(false,Path::new(&actdir).exists());
        }
    }
    mod open_with {
        use std::path::Path;
        use maketemp::TempDir;
        
        #[test]
        fn give_unauthorized_dir_return_error() {
            let dir = "/root";
            let prefix = "abc-";
            
            {
                match TempDir::open_with(dir,prefix) {
                    Ok(v) => { panic!("unexpected state. ({})",v.path()); },
                    Err(_msg) => { /* OK! */ }
                }
            }
        }
        #[test]
        fn give_valid_values_return_done() {
            let dir = std::env::current_dir().unwrap();
            let prefix = "abc-";
            let actdir;
            
            {
                let obj = match TempDir::open_with(dir,prefix) {
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