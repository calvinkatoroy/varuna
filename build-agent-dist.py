"""Stage what Caddy serves at /dist: the installer script and the CURRENT agent code.
Run it whenever the agent changes (start-varuna.ps1 does it on every start), so clients never
install a stale agent. Standard library only."""
import pathlib
import shutil
import zipfile

root = pathlib.Path(__file__).parent
dist = root / "agent-dist"
dist.mkdir(exist_ok=True)
shutil.copyfile(root / "agent" / "install.ps1", dist / "install.ps1")
with zipfile.ZipFile(dist / "agent-bundle.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for f in [root / "agent" / "agent.py", root / "agent" / "scan.py", *sorted((root / "agent" / "tools").glob("*.py"))]:
        z.write(f, f.relative_to(root / "agent").as_posix())
print("staged agent-dist:", ", ".join(sorted(z.name for z in dist.iterdir() if z.name != ".gitkeep")))
