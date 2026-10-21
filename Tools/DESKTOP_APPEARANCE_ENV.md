# Desktop appearance prototype environment

Verified on 2026-10-18. This records dependency and API preparation; it does not claim the experiment, headset integration, or Unity build has passed.

- SSH alias: `desktop-ubuntu-ts`.
- Checkout: `/home/enjixiong/academics/AIAA4435/AIAA4435-Project`.
- Unity editor: `/home/enjixiong/Unity/Hub/Editor/2022.3.62f3c1/Editor/Unity`.
- Existing desktop display: `DISPLAY=:1`, `XAUTHORITY=/home/enjixiong/.Xauthority`. `xdpyinfo` connected successfully. These variables refer to the user's existing desktop session; no new display or access rule was created.

## Exact external packages

The repository's `Packages/manifest.json` and project settings were preserved. Its existing relative package paths now resolve:

| Package | Version and source | Desktop path |
|---|---|---|
| PICO Integration | 3.4.0, official tag `release_3.4.0`, commit `e0740bf309b26a0b9adae33c506514569bfe5d38` | `/home/enjixiong/academics/AIAA4435/PICO Unity Integration SDK-3.4.0-20260226` |
| Unity MCP | 10.3.0, commit `aa5fc638d623f56178d50329d9ad8c541a57fe66` | `/home/enjixiong/academics/AIAA4435/Tools/unity-mcp/MCPForUnity` |

The PICO folder name preserves the manifest's expected path. Its contents come from the official GitHub 3.4.0 release, not from a comparison against a separately downloaded ZIP carrying that date suffix. The pre-existing 3.1.2 SDK in the week 5 homework was left untouched. Package sources remain outside this repository; their upstream licenses apply.

Sources: [PICO 3.4.0 release](https://github.com/Pico-Developer/PICO-Unity-Integration-SDK/releases/tag/release_3.4.0), [Unity MCP pinned commit](https://github.com/CoplayDev/unity-mcp/commit/aa5fc638d623f56178d50329d9ad8c541a57fe66).

## Git LFS assets

The initial desktop clone contained 74 Git LFS pointers under `Assets`. Installed the official Linux amd64 Git LFS 3.8.0 binary at `/home/enjixiong/.local/bin/git-lfs`, verified the release archive SHA-256, and fetched the project assets. The final scan found **zero remaining LFS pointers under `Assets`**. The PICO SDK's one LFS sample asset required an explicit `git lfs fetch origin release_3.4.0` and `git lfs checkout` after the initial pull. Both the project and SDK subsequently passed `git lfs fsck`. `git lfs install --local` was used in these two new clones; system packages and global Git configuration were not modified.

Official archive: [Git LFS 3.8.0](https://github.com/git-lfs/git-lfs/releases/tag/v3.8.0). Verified archive SHA-256: `e455e00f15d9b95661b8d53498ffb0c3367962cf1ec73c31ab7369516cd6ab8d`.

## Existing DeepSeek credential

The desktop's existing DeepSeek provider was found in `~/.cc-switch/cc-switch.db`. The source configuration was read without changing it or printing the credential. Its Anthropic-compatible endpoint was `https://api.deepseek.com/anthropic`; the prototype uses the same official service's OpenAI-compatible endpoint `https://api.deepseek.com`.

A real, minimal request succeeded: requested model `deepseek-v4-flash`, returned model `deepseek-flash`, 9 prompt tokens and 1 completion token. This verifies authentication and model availability at preparation time, not future service availability or an immutable model version.

The backend environment file is `/home/enjixiong/.config/aiaa4435/appearance.env`, mode `0600`. It defines `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, and `DEEPSEEK_MODEL`. Nonsecret provenance is saved beside it in `appearance.provider.json`. Neither credential file belongs in Git or a Unity build.

Load the environment only in the backend process:

```bash
set -a
. /home/enjixiong/.config/aiaa4435/appearance.env
set +a
```

Use the backend's documented launch command after loading those variables. Do not use shell tracing (`set -x`) or print the environment. The Unity client communicates with the backend and does not receive the API key.

For later Git LFS commands, ensure the user-local directory is available:

```bash
export PATH=/home/enjixiong/.local/bin:$PATH
```

The 74 project assets were subsequently copied back into the local WSL working copy. Each file was checked against its original LFS pointer's SHA-256 and byte size before replacing that pointer. Only those listed assets were transferred; application source files were not copied over. The reproducible asset manifest is `Tools/AppearanceExperiment/local-lfs-materialization.json`.

Run the static source and study-material audit from either complete checkout:

```bash
python3 Tools/AppearanceExperiment/verify_source.py
```

Its report is `Docs/AppearanceExperiment/Validation/source-checks.json`. It checks asset integrity and authored task/schedule/questionnaire joins, and explicitly does not claim a Unity build, browser interaction or participant study has passed.

Setup did not launch Unity, change the existing room, or edit another homework project. See the implementation/build verification report for subsequent prototype results.
