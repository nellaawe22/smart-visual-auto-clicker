# Smart Visual Auto-Clicker — Windows EXE build

This package contains the app source and a GitHub Actions workflow that builds a standalone Windows 10/11 64-bit `.exe` on a Windows build runner. The resulting app does not require Python to be installed on your PC.

## Build the EXE (no Python needed on your PC)

1. Sign in to GitHub or create a free account.
2. Create a new repository, for example `smart-visual-auto-clicker`.
3. Upload the contents of this folder to the repository. Make sure the `.github/workflows/build-windows.yml` file is included.
4. Open the repository's **Actions** tab.
5. Select **Build Windows EXE** and click **Run workflow** (or push the files to the `main` branch).
6. When the run finishes successfully, open that run and download the artifact named `SmartVisualAutoClicker-Windows-x64`.
7. Extract the artifact. It contains `SmartVisualAutoClicker.exe`. Double-click to run.

## What is included

- Mouse and keyboard recording
- Playback with adjustable speed
- Fixed loop count or infinite loop
- Save/load recordings as JSON
- Screen image matching for Chrome tab favicons and webpage logos
- Optional automatic click on a detected match

## Important notes

- I cannot compile a genuine Windows `.exe` in this Linux build environment. The included workflow performs the build on a real Windows runner. Your PC does not need Python; GitHub account is needed for this build route.
- Windows may show a SmartScreen warning because this is an unsigned, locally built executable. Only run it if you trust the source and have reviewed the project.
- Screen image matching only scans what is visible. It cannot inspect hidden/background Chrome tabs.
- Recorded mouse actions use screen coordinates; window movement or display scaling changes may affect playback.
- Do not record passwords, payment details, or private customer information. Use only where you have authorization.
- Test with harmless actions first. Stop playback if it behaves unexpectedly.
