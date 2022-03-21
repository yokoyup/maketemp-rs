#!/usr/bin/python
# coding:utf-8

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time

class CargoTestReport(object):
    
    def __init__(self,records):
        """
        新しいCargoTestReportインスタンスを生成します。
        
        - `records` - テストレコード
        """
        self.__records = records
    
    def stats(self):
        """
        統計情報を返します。
        """
        res = { "test_count":0,"passed":0,"failed":0,"allowed_fail":0,"ignored":0,"exec_time":0 }
        for t in self.__records:
            if t["type"] != "suite":
                continue
            if t["event"] == "started":
                res["test_count"] += t["test_count"]
            elif t["event"] == "ok":
                res["passed"] += t["passed"]
                res["failed"] += t["failed"]
                res["allowed_fail"] += t["allowed_fail"]
                res["ignored"] += t["ignored"]
                res["exec_time"] += t["exec_time"]
            else:
                continue
        return res
    
    def fails(self):
        """
        失敗したテストの情報を返します。
        """
        fails = []
        for t in self.__records:
            if t["type"] != "test":
                continue
            if t["event"] != "failed":
                continue
            fails.append(t)
        return fails

class VirtualBoxMachine(object):
    
    def __init__(self,name):
        running = False
        for vm in self.__running_vms():
            if vm == name:
                running = True
        
        if not running:
            self.__launch(name)
        
        self.__name = name
    
    def close(self):
        st = subprocess.run([ "VBoxManage","controlvm",self.__name,"poweroff" ],stdout=sys.stdout,stderr=sys.stderr)
        if st.returncode != 0:
            raise Exception("error occurred. stop. (%d)" % (st.returncode))
    
    def command(self,args):
        st = self.__command(self.__name,args)
        if st.returncode != 0:
            raise Exception("error occurred. stop. (%d)" % (st.returncode))
    
    def mkdir(self,guestdir):
        a = [ "VBoxManage","guestcontrol",self.__name,"mkdir","--username","root","--password","sukima",guestdir ]
        
        st = subprocess.run(a,stdout=sys.stdout,stderr=sys.stderr)
        if st.returncode != 0:
            raise Exception("error occurred. stop. (%d)" % (st.returncode))
    
    def mktemp(self,is_directory):
        a = [ "VBoxManage","guestcontrol",self.__name,"mktemp","--username","root","--password","sukima" ]
        if is_directory:
            a.append("--directory")
            a.extend([ "--tmpdir","/tmp" ])
        a.append("tmp-XXX")
        
        st = subprocess.run(a,stdout=subprocess.PIPE,stderr=sys.stderr)
        if st.returncode != 0:
            raise Exception("error occurred. stop. (%d)" % (st.returncode))
        
        so = st.stdout.decode("utf-8")
        for m in re.finditer(r"(?m)^Directory name: (.*?)$",so):
            return m[1]
        raise Exception("unexpected stdout. (%s)" % (so))
    
    def copyfrom(self,guestdir,hostdir):
        a = [ "VBoxManage","guestcontrol",self.__name,"copyfrom","--username","root","--password","sukima","--recursive","--target-directory",hostdir,guestdir ]
        
        st = subprocess.run(a,stdout=sys.stdout,stderr=sys.stderr)
        if st.returncode != 0:
            raise Exception("error occurred. stop. (%d)" % (st.returncode))
    
    def copyto(self,hostdir,guestdir):
        a = [ "VBoxManage","guestcontrol",self.__name,"copyto","--username","root","--password","sukima","--recursive",hostdir,guestdir ]
        
        st = subprocess.run(a,stdout=sys.stdout,stderr=sys.stderr)
        if st.returncode != 0:
            raise Exception("error occurred. stop. (%d)" % (st.returncode))
    
    def __launch(self,name):
        st = subprocess.run([ "VBoxManage","startvm",name ],stdout=sys.stdout,stderr=sys.stderr)
        if st.returncode != 0:
            raise Exception("error occurred. stop. (%d)" % (st.returncode))
        
        while True:
            st = self.__command(name,[ "/bin/echo","hello" ])
            if st.returncode == 0:
                break
            time.sleep(1)
    
    def __running_vms(self):
        st = subprocess.run([ "VBoxManage","list","runningvms" ],stdout=subprocess.PIPE,stderr=sys.stderr)
        if st.returncode != 0:
            raise Exception("error occurred. stop. (%d)" % (st.returncode))
        
        vms = []
        for m in re.finditer(r"(?m)^\"(.*?)\"",st.stdout.decode("utf-8")):
            vms.append(m[1])
        return vms
    
    def __command(self,name,args):
        a = [ "VBoxManage","guestcontrol",name,"run","--username","root","--password","sukima","--exe" ]
        a.append(args.pop(0))
        a.extend([ "--","." ])
        a.extend(args)
        
        return subprocess.run(a,stdout=sys.stdout,stderr=sys.stderr)

class Cargo(object):
    
    def __init__(self,cargo_file):
        self.__cargo_file = cargo_file
    
    def build(self,project_dir):
        """
        ビルドします。
        
        - `project_dir` - プロジェクトのディレクトリーパス
        """
        args = [ self.__cargo_file,"build","--release" ]
        env = os.environ
        st = subprocess.run(args,stdout=sys.stdout,stderr=sys.stderr,cwd=project_dir,env=env)
        if st.returncode != 0:
            raise Exception("error occurred. stop. (%d)" % (st.returncode))
    
    def run(self,project_dir,args):
        """
        実行します。
        
        - `project_dir` - プロジェクトのディレクトリーパス
        - `args`        - プログラムに渡す引数
        """
        cargs = [ self.__cargo_file,"run","--release" ]
        if 0 < len(args):
            cargs.append("--")
            cargs.extend(args)
        
        env = os.environ
        st = subprocess.run(cargs,stdout=sys.stdout,stderr=sys.stderr,cwd=project_dir,env=env)
        if st.returncode != 0:
            raise Exception("error occurred. stop. (%d)" % (st.returncode))

    def test(self,project_dir,features,testreport_file,covreport_dir,threads):
        """
        ユニットテストを実行します。
        
        - covreport_dir を指定すると、カバレッジ測定も合わせて行います
        
        - `project_dir`     - プロジェクトのディレクトリーパス
        - `features`        - フィーチャー
        - `testreport_file` - ユニットテストレポートの出力先ファイルパス
        - `covreport_dir`   - カバレッジレポートの出力先ディレクトリーパス。不要の場合は None を指定可能
        - `threads`         - テストを並行実行する数
        """
        # llvm-tools-preview がインストールされているかどうかをチェック
        # - カバレッジ測定に必要
        st = subprocess.run([
            "rustup","component","list","--installed"
        ],cwd=project_dir,stdout=subprocess.PIPE,stderr=sys.stderr)
        if st.returncode != 0:
            raise Exception("unexpected error occurred. stop. (%d)" % (st.returncode))
        if re.search(r"(?m)^llvm-tools-preview-.*$",st.stdout.decode("utf-8")) is None:
            raise Exception("please install `llvm-tools-preview` component by `rustup component add`.")
        
        # テストレポートより新しい更新がない場合はスキップする
        if os.path.exists(testreport_file):
            t = cargo_project_last_modification_timestamp(project_dir)
            if t < os.stat(testreport_file).st_mtime:
                print("[SKIP] cargo test (%s: no modified)" % (project_dir))
                return
        
        args = [ self.__cargo_file,"test" ]
        if 0 < len(features):
            args.append("--features")
            args.extend(features)
        args.extend([ "--","-Z","unstable-options","--format","json","--report-time" ])
        if threads is not None:
            args.append("--test-threads=%d" % (threads))
        
        profdir = os.path.join(project_dir,"tmp")
        utstts  = None
        
        env = os.environ
        env["RUSTC_BOOTSTRAP"] = "1"
        env["RUSTFLAGS"] = "-Zinstrument-coverage"
        env["LLVM_PROFILE_FILE"] = os.path.join(profdir,"cov-%p-%m.profraw")
        
        try:
            if not os.path.exists(os.path.dirname(testreport_file)):
                os.makedirs(os.path.dirname(testreport_file))
            
            with open(testreport_file,"w+b") as f:
                utstts = subprocess.run(args,cwd=project_dir,stdout=f,stderr=sys.stderr,env=env)
            # テストレポートをjson形式に正す
            with open(testreport_file,"r+") as f:
                data = f.read()
                
                data = re.sub(r"(?m)\}$","},",data)
                data = re.sub(r",[\s]*\Z","",data)
                
                f.seek(0)
                f.write("[")
                f.write(data)
                f.write("]")
            
            # カバレッジレポートを作成
            # - HTML形式
            # - Cobertura形式
            st = subprocess.run([
                "grcov",profdir,"-s",project_dir,"--binary-path",os.path.join(project_dir,"target/debug/"),"-t","html","--branch","--ignore-not-existing","-o",covreport_dir
            ],cwd=project_dir,stdout=sys.stdout,stderr=sys.stderr,env=env)
            st = subprocess.run([
                "grcov",profdir,"-s",project_dir,"--binary-path",os.path.join(project_dir,"target/debug/"),"-t","cobertura","--branch","--ignore-not-existing","-o",os.path.join(covreport_dir,"cobertura.xml")
            ],cwd=project_dir,stdout=sys.stdout,stderr=sys.stderr,env=env)
        finally:
            if os.path.exists(profdir):
                shutil.rmtree(profdir)
            
            # 2021.11.30 yocotch
            # 後続の処理で os.environ を参照すると、含まれたままになってしまうため、ここで削除する
            del env["RUSTC_BOOTSTRAP"]
            del env["RUSTFLAGS"]
            del env["LLVM_PROFILE_FILE"]
        
        titems = []
        with open(testreport_file,"rb") as f:
            titems = json.load(f)
        ctr = CargoTestReport(titems)
        
        if utstts.returncode != 0:
            fails = []
            for t in ctr.fails():
                fails.append(t["name"] + ":")
                fails.append(re.sub(r"(?m)^","    ",t["stdout"]))
            
            raise Exception("error occurred. stop. (%d)\n\n%s" % (utstts.returncode,"\n".join(fails)))
        
        sts = ctr.stats()
        print(
            "%d tests, %d passed, %d failed, %d allowed_fail, %d ignored.\ntotal time %.3f s."
            % (sts["test_count"],sts["passed"],sts["failed"],sts["allowed_fail"],sts["ignored"],sts["exec_time"])
        )

    def doc(self,project_dir,out_dir):
        """
        ドキュメントを作成します。
        
        - `project_dir` - プロジェクトのディレクトリーパス
        - `out_dir`     - ドキュメントの出力先ディレクトリーのパス。`None`の場合はデフォルトの出力先に出力されます（targets）。
        """
        args = [ self.__cargo_file,"doc","--no-deps" ]
        if not out_dir is None:
            args.extend([ "--target-dir",out_dir ])
        
        env = os.environ
        st = subprocess.run(args,stdout=sys.stdout,stderr=sys.stderr,cwd=project_dir,env=env)
        if st.returncode != 0:
            raise Exception("error occurred. stop. (%d)" % (st.returncode))

def last_modification_timestamp(dir):
    """
    ディレクトリーの中にあるもののうち、最後に更新したファイルの日時を返します。
    
    - `dir` - ディレクトリーのパス
    """
    t = os.stat(dir).st_mtime
    
    for en in os.listdir(dir):
        p = os.path.join(dir,en)
        s = os.stat(p)
        if t < s.st_mtime:
            t = s.st_mtime
        if os.path.isdir(p):
            tt = last_modification_timestamp(p)
            if t < tt:
                t = tt
    return t

def cargo_project_last_modification_timestamp(project_dir):
    """
    cargoプロジェクトの中にあるもののうち、最後に更新したファイルの日時を返します。
    
    - 2021.12.4時点では、次の3つを対象にしています
      - Cargo.toml
      - src ディレクトリー
      - tests ディレクトリー
    - 今後リソースファイルも対象にする必要がありそうです
    
    - `dir` - ディレクトリーのパス
    """
    t = os.stat(os.path.join(project_dir,"Cargo.toml")).st_mtime
    
    tgtdirs = [
        os.path.join(project_dir,"src"),
        os.path.join(project_dir,"tests")
    ]
    for d in tgtdirs:
        if not os.path.exists(d):
            continue
        tt = last_modification_timestamp(d)
        if tt <= t:
            continue
        t = tt
    
    return t

def wasm_pack_build(project_dir,out_dir):
    """
    wasm-packでビルドします。
    
    - `project_dir` - プロジェクトのディレクトリーパス
    - `out_dir`     - 出力先ディレクトリーのパス
    """
    args = [
        "wasm-pack","build","--release","--target","web","--out-name","wasm","--out-dir",out_dir
    ]
    env = os.environ
    env["RUSTFLAGS"] = "--cfg=web_sys_unstable_apis"
    
    try:
        st = subprocess.run(args,stdout=sys.stdout,stderr=sys.stderr,cwd=project_dir,env=env)
        if st.returncode != 0:
            raise Exception("error occurred. stop. (%d)" % (st.returncode))
    finally:
        del env["RUSTFLAGS"]

def run_command(basedir,args,env):
    """
    コマンドを実行します。
    
    - `basedir` - 基準ディレクトリーのパス
    - `args`    - コマンド
    - `env`     - 環境変数
    """
    
    ekv = os.environ
    for k,v in env.items():
        ekv[k] = v
    
    try:
        st = subprocess.run(args,stdout=sys.stdout,stderr=sys.stderr,cwd=basedir,env=ekv)
        if st.returncode != 0:
            raise Exception("error occurred. stop. (%d)" % (st.returncode))
    finally:
        for k in env.keys():
            del ekv[k]

def md5_of_file(file):
    md5 = hashlib.md5()
    with open(file,"rb") as f:
        md5.update(f.read(4096))
    return md5.hexdigest()

def merge_tree(source_dir,dest_dir):
    """
    ディレクトリーツリーをマージします。
    
    - `source_dir` - マージ元のディレクトリー
    - `dest_dir`   - マージ先のディレクトリー
    """
    print("%s to %s" % (source_dir,dest_dir))
    
    if not os.path.exists(dest_dir):
        os.mkdir(dest_dir)
    
    for pdir,dirs,files in os.walk(source_dir):
        for en in dirs:
            p = os.path.relpath(os.path.join(pdir,en),source_dir)
            print("%-32s   " % (p + "/"),end="")
            dest = os.path.join(dest_dir,p)
            
            if not os.path.exists(dest):
                os.mkdir(dest)
                print("created")
            else:
                print("skip")
        
        for en in files:
            src = os.path.join(pdir,en)
            p = os.path.relpath(src,source_dir)
            print("%-32s   " % (p),end="")
            dest = os.path.join(dest_dir,p)
            
            smd5 = md5_of_file(src)
            dmd5 = md5_of_file(dest) if os.path.exists(dest) else None
            if smd5 == dmd5:
                print("skip")
                continue
            
            shutil.copyfile(src,dest)
            print("copied")

def load_build_config(path):
    """
    ビルド設定をロードします。
    
    - `path` - パス
    """
    if not os.path.exists(path):
        raise Exception("build.json not found in `%s`" % (os.path.dirname(path)))
    
    try:
        with open(path,"rb") as f:
            return json.load(f)
    except Exception as err:
        raise Exception("can't load build.json: %s" % (str(err)))

DEFAULT_ENV = {
    "cargo":"cargo"
}

def load_environment_config(path):
    """
    ビルド設定をロードします。
    
    - `path` - パス
    """
    obj = {}
    if os.path.exists(path):
        try:
            with open(path,"rb") as f:
                obj = json.load(f)
        except Exception as err:
            raise Exception("can't load build.json: %s" % (str(err)))
    
    for k,v in DEFAULT_ENV.items():
        if k in obj:
            continue
        obj[k] = v
    
    return obj

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent('''\
            build.json にサブコマンドを追加し、以下の操作を複数、順番自由に行うことができます。
            
            サポートしている操作:
              - cargo-build   リリースビルドします
              - cargo-run     リリースビルドして実行します
              - cargo-test    テストを実行します
              - cargo-doc     ドキュメントを作成します
              - mkdir         ディレクトリーを作成します
              - copy          ディレクトリーをコピーします
              - delete        ファイルやディレクトリーを削除します
              - wasm-pack     Web Assemblyを作成します
              - command       任意のコマンドを実行します
              - virtual-box-open      VirtualBoxの仮想マシンを起動します
              - virtual-box-close     VirtualBoxの仮想マシンを終了します
              - virtual-box-command   VirtualBoxの仮想マシンで任意のコマンドを実行します
              - virtual-box-build     VirtualBoxの仮想マシンでリリースビルドします
        ''')
    )
    ap.add_argument("name",nargs=1,help="build.json に宣言されたサブコマンドを指定します")
    ap.add_argument("program_args",nargs="*")
    
    apargs = ap.parse_args(sys.argv[1:])
    if hasattr(apargs,"help"):
        ap.print_help()
        sys.exit(1)
    
    runname = apargs.name[0]
    
    mydir   = os.path.dirname(os.path.abspath(__file__))
    scripts = load_build_config(os.path.join(mydir,"build.json"))
    envs    = load_environment_config(os.path.join(mydir,"env.json"))
    
    if not runname in scripts:
        print("name not found in build.json. (%s)" % (runname),file=sys.stderr)
        sys.exit(3)
    
    cmds = scripts[runname]
    for cmd in cmds:
        op = cmd["op"]
        args = cmd["args"]
        
        if op == "cargo-build":
            tgt = os.path.join(mydir,args["dir"])
            
            c = Cargo(envs["cargo"])
            c.build(tgt)
        elif op == "cargo-run":
            tgt = os.path.join(mydir,args["dir"])
            
            c = Cargo(envs["cargo"])
            c.run(tgt,apargs.program_args)
        elif op == "cargo-test":
            tgt    = os.path.join(mydir,args["dir"])
            rptdir = os.path.join(mydir,args["report-dir"])
            
            c = Cargo(envs["cargo"])
            c.test(
                tgt,args["features"],
                os.path.join(rptdir,"unittest","report.json"),
                os.path.join(rptdir,"coverage"),
                args["threads"]
            )
        elif op == "cargo-doc":
            tgt = os.path.join(mydir,args["dir"])
            out = None
            if "out" in args:
                out = os.path.join(mydir,args["out"])
            
            c = Cargo(envs["cargo"])
            c.doc(tgt,out)
        elif op == "mkdir":
            os.mkdir(args["target"])
        elif op == "copy":
            merge_tree(
                os.path.join(mydir,args["source"]),
                os.path.join(mydir,args["dest"])
            )
        elif op == "delete":
            tgt = os.path.join(mydir,args["target"])
            
            if os.path.exists(tgt):
                if os.path.isdir(tgt):
                    shutil.rmtree(tgt)
                elif os.path.isfile(tgt):
                    os.remove(tgt)
                else:
                    raise Exception("unexpected state. (%s)" % (tgt))
        elif op == "wasm-pack":
            tgt = os.path.join(mydir,args["dir"])
            
            wasm_pack_build(tgt,os.path.join(mydir,args["out"]))
        elif op == "command":
            tgt = os.path.join(mydir,args["dir"])
            
            run_command(tgt,args["args"],args["env"])
        elif op == "virtual-box-open":
            vbm = VirtualBoxMachine(args["vm"])
        elif op == "virtual-box-close":
            vbm = VirtualBoxMachine(args["vm"])
            vbm.close()
        elif op == "virtual-box-command":
            vbm = VirtualBoxMachine(args["vm"])
            vbm.command(args["args"])
        elif op == "virtual-box-cargo-build":
            vbm = VirtualBoxMachine(args["vm"])
            
            outdir = os.path.join(mydir,args["output"])
            
            tmpdir = tempfile.mkdtemp()
            envfile = os.path.join(tmpdir,"env.json")
            with open(envfile,"w+") as f:
                json.dump({ "cargo":args["cargo"] },f)
            
            try:
                projdir = vbm.mktemp(True)
                vbm.copyto(mydir,projdir)
                vbm.copyto(envfile,projdir)
                vbm.command([ "/usr/local/bin/python3",projdir + "/build.py","build" ])
                vbm.copyfrom(projdir + "/target",outdir)
            finally:
                shutil.rmtree(tmpdir)
        else:
            print("unsupported op. (%s)" % (op),file=sys.stderr)
            sys.exit(4)