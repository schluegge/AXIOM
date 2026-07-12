use std::env;
use std::ffi::OsStr;
use std::process::{Command, ExitCode};

fn run(program: &str, args: &[&str]) -> Result<(), String> {
    let status = Command::new(program)
        .args(args)
        .status()
        .map_err(|error| format!("failed to execute {program}: {error}"))?;
    if status.success() {
        Ok(())
    } else {
        Err(format!("command failed ({status}): {program} {}", args.join(" ")))
    }
}

fn run_python(args: &[&str]) -> Result<(), String> {
    for candidate in ["python", "python3", "py"] {
        let mut command = Command::new(candidate);
        if candidate == "py" {
            command.arg("-3");
        }
        command.args(args);
        match command.status() {
            Ok(status) if status.success() => return Ok(()),
            Ok(status) => return Err(format!("Python command failed with {status}")),
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => continue,
            Err(error) => return Err(format!("failed to execute Python: {error}")),
        }
    }
    Err("no Python 3 executable found".to_string())
}

fn check() -> Result<(), String> {
    run("cargo", &["fmt", "--all", "--", "--check"])?;
    run(
        "cargo",
        &[
            "clippy",
            "--workspace",
            "--all-targets",
            "--all-features",
            "--",
            "-D",
            "warnings",
        ],
    )?;
    run("cargo", &["test", "--workspace", "--all-features"])?;
    run_python(&["tools/legacy_inventory.py", "--check"])?;
    run_python(&["tools/check_mvp_contract.py"])?;
    Ok(())
}

fn main() -> ExitCode {
    let command = env::args_os().nth(1).unwrap_or_else(|| OsStr::new("check").to_owned());
    let result = match command.to_str() {
        Some("check" | "test" | "proof") => check(),
        Some(other) => Err(format!("unknown xtask command: {other}")),
        None => Err("xtask command is not valid UTF-8".to_string()),
    };
    match result {
        Ok(()) => ExitCode::SUCCESS,
        Err(error) => {
            eprintln!("{error}");
            ExitCode::FAILURE
        }
    }
}
