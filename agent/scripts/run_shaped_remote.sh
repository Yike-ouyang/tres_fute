#!/usr/bin/env bash
# Server-side runner for the rl_env_2 shaped-reward training.
#
# Runs entirely on the remote host (astragale): it does NOT copy files.
# It regenerates agent/rl_env_2/train_shaped.py from the marimo notebook
# (single source of truth), launches the three variants (min_zone, pbrs,
# variance) in parallel as detached processes, and starts TensorBoard bound
# to 127.0.0.1 (reachable through an SSH tunnel).
#
# Layout: code + runs live under agent/, game_engine/simulation under backend/,
# and the shared virtualenv is at the repository root (.venv).
#
# Prerequisites on the server (once):
#   * repo cloned                             -> agent/runs/ must exist
#   * models copied from the local machine    -> see "sync models" below
#   * agent/scripts/run_shaped_remote.sh install   (venv + dependencies)
#
# Local -> server model copy (run from the LOCAL repo root):
#   rsync -avR \
#     agent/runs/essai_01/best_model.zip \
#     agent/runs/solo_*/score_delta_solo/best_model.zip \
#     astragale.polytechnique.fr:~/tres_fute/
#
# SSH tunnel to watch TensorBoard from the local browser:
#   ssh -N -L 6007:127.0.0.1:6006 astragale.polytechnique.fr
#   # then open http://localhost:6007
#
# Start origin (start command):
#   default              -> from scratch (blank MaskablePPO policy)
#   --no-from-scratch    -> from the latest agent/runs/solo_*/score_delta_solo/best_model.zip
#   --start-from PATH    -> from an explicit checkpoint
#
# Usage:
#   agent/scripts/run_shaped_remote.sh install
#   agent/scripts/run_shaped_remote.sh start [options]
#   agent/scripts/run_shaped_remote.sh status [--output-dir DIR]
#   agent/scripts/run_shaped_remote.sh logs   [--output-dir DIR]
#   agent/scripts/run_shaped_remote.sh stop   [--output-dir DIR] [--all]
#   agent/scripts/run_shaped_remote.sh tensorboard [--host H] [--port P] [--output-dir DIR]
#   agent/scripts/run_shaped_remote.sh replays [--seed N] [--output-dir DIR]
#   agent/scripts/run_shaped_remote.sh help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AGENT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"           # agent/ (rl_env, rl_env_2, runs)
REPO_ROOT="$(cd "$AGENT_DIR/.." && pwd)"            # repository root
BACKEND_DIR="$REPO_ROOT/backend"                    # backend/ (game_engine, simulation)
VENV="$REPO_ROOT/.venv"                             # shared virtualenv (repo root)
PY="$VENV/bin/python"
NOTEBOOK="$AGENT_DIR/rl_env_2/shaped_reward_training.py"
TRAIN_SCRIPT="$AGENT_DIR/rl_env_2/train_shaped.py"
RUNS="$AGENT_DIR/runs"
LAST_FILE="$RUNS/.shaped_last"
REMOTE_HOST="${TRES_FUTE_REMOTE_HOST:-astragale.polytechnique.fr}"
TUNNEL_PORT="${TRES_FUTE_TUNNEL_PORT:-6007}"

# Defaults mirror the notebook CONFIG.
TIMESTEPS=2000000
N_ENVS=4
N_STEPS=2048
BATCH_SIZE=128
N_EPOCHS=10
LEARNING_RATE=3e-4
ENT_COEF=0.01
GAMMA=0.999
ALPHA=0.05
BETA=0.01
PHI_SCALE=0.01
SEED=42
EVAL_SEED=1000000
EVAL_EPISODES=200
EVAL_EVERY=50000
CHECKPOINT_EVERY=200000
DEVICE=cpu
TORCH_THREADS=1
START_FROM=""
FROM_SCRATCH=1
CHECKPOINT="$RUNS/essai_01/best_model.zip"
OUTPUT_DIR=""
MODES="min_zone,pbrs,variance"
WITH_TENSORBOARD=1
TB_HOST=127.0.0.1
TB_PORT=6006
REPLAY_SEED=2000000

die() { echo "ERROR: $*" >&2; exit 1; }

usage() {
    sed -n '2,40p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

require_venv() {
    [ -x "$PY" ] || die "venv manquant ($VENV). Lance d'abord: $0 install"
}

latest_solo_best() {
    ls -1t "$RUNS"/solo_*/score_delta_solo/best_model.zip 2>/dev/null | head -n1 || true
}

resolve_out() {
    if [ -n "$OUTPUT_DIR" ]; then
        printf '%s' "$OUTPUT_DIR"
    elif [ -f "$LAST_FILE" ]; then
        cat "$LAST_FILE"
    else
        ls -1dt "$RUNS"/shaped_* 2>/dev/null | head -n1 || true
    fi
}

regenerate_train_script() {
    [ -f "$NOTEBOOK" ] || die "notebook introuvable: $NOTEBOOK"
    "$PY" - "$NOTEBOOK" "$TRAIN_SCRIPT" <<'PY'
import ast
import pathlib
import sys
import textwrap

notebook, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
lines = notebook.read_text(encoding="utf-8").splitlines()
try:
    start = next(i for i, l in enumerate(lines) if "textwrap.dedent('''" in l)
    end = next(i for i, l in enumerate(lines) if i > start and l.strip() == "''').strip()")
except StopIteration:
    raise SystemExit("Impossible de localiser TRAINING_SCRIPT dans le notebook")
script = textwrap.dedent("\n".join(lines[start + 1:end])) + "\n"
ast.parse(script)
out.write_text(script, encoding="utf-8")
print(f"train_shaped.py régénéré: {out}")
PY
}

start_tensorboard() {
    local out="$1" host="$2" port="$3"
    command -v tensorboard >/dev/null 2>&1 || { echo "tensorboard introuvable (pip install tensorboard)"; return 0; }
    nohup tensorboard --logdir "$out" --host "$host" --port "$port" \
        > "$out/tensorboard.log" 2>&1 < /dev/null &
    echo "tensorboard $!" >> "$out/pids"
    echo "TensorBoard lancé sur $host:$port (log: $out/tensorboard.log)"
}

cmd_install() {
    # Venv général à la racine, torch CPU (pas de CUDA inutile).
    if command -v uv >/dev/null 2>&1; then
        uv venv "$VENV" --python 3.12
        uv pip install --python "$PY" --index-url https://download.pytorch.org/whl/cpu torch
        uv pip install --python "$PY" \
            stable-baselines3==2.9.0 \
            sb3-contrib==2.9.0 \
            gymnasium==1.3.0 \
            numpy \
            tensorboard \
            marimo==0.24.2 \
            fastapi \
            "uvicorn[standard]" \
            matplotlib \
            pytest \
            httpx2
    else
        python3 -m venv "$VENV"
        "$VENV/bin/pip" install --upgrade pip
        "$VENV/bin/pip" install torch --index-url https://download.pytorch.org/whl/cpu
        "$VENV/bin/pip" install \
            stable-baselines3==2.9.0 \
            sb3-contrib==2.9.0 \
            gymnasium==1.3.0 \
            numpy \
            tensorboard \
            marimo==0.24.2 \
            fastapi \
            "uvicorn[standard]" \
            matplotlib \
            pytest \
            httpx2
    fi
    echo "Installation terminée dans $VENV"
    echo "Note: backend/requirements.txt est un freeze complet avec CUDA/NVIDIA; on ne l'utilise pas ici."
}

parse_start_opts() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --timesteps) TIMESTEPS="$2"; shift 2;;
            --n-envs) N_ENVS="$2"; shift 2;;
            --n-steps) N_STEPS="$2"; shift 2;;
            --batch-size) BATCH_SIZE="$2"; shift 2;;
            --n-epochs) N_EPOCHS="$2"; shift 2;;
            --learning-rate) LEARNING_RATE="$2"; shift 2;;
            --ent-coef) ENT_COEF="$2"; shift 2;;
            --gamma) GAMMA="$2"; shift 2;;
            --alpha) ALPHA="$2"; shift 2;;
            --beta) BETA="$2"; shift 2;;
            --phi-scale) PHI_SCALE="$2"; shift 2;;
            --seed) SEED="$2"; shift 2;;
            --eval-seed) EVAL_SEED="$2"; shift 2;;
            --eval-episodes) EVAL_EPISODES="$2"; shift 2;;
            --eval-every) EVAL_EVERY="$2"; shift 2;;
            --checkpoint-every) CHECKPOINT_EVERY="$2"; shift 2;;
            --device) DEVICE="$2"; shift 2;;
            --torch-threads) TORCH_THREADS="$2"; shift 2;;
            --start-from) START_FROM="$2"; FROM_SCRATCH=0; shift 2;;
            --from-scratch) FROM_SCRATCH=1; shift;;
            --no-from-scratch) FROM_SCRATCH=0; shift;;
            --checkpoint) CHECKPOINT="$2"; shift 2;;
            --output-dir) OUTPUT_DIR="$2"; shift 2;;
            --modes) MODES="$2"; shift 2;;
            --tensorboard) WITH_TENSORBOARD=1; shift;;
            --no-tensorboard) WITH_TENSORBOARD=0; shift;;
            --tb-host) TB_HOST="$2"; shift 2;;
            --tb-port) TB_PORT="$2"; shift 2;;
            -h|--help) usage; exit 0;;
            *) die "option inconnue pour start: $1";;
        esac
    done
}

cmd_start() {
    parse_start_opts "$@"
    require_venv

    [ -f "$CHECKPOINT" ] || die "adversaire checkpoint introuvable: $CHECKPOINT
Copie-le depuis ta machine locale (depuis la racine du repo local):
  rsync -avR agent/runs/essai_01/best_model.zip $REMOTE_HOST:~/tres_fute/"

    if [ "$FROM_SCRATCH" = 1 ]; then
        ORIGIN="scratch"
        ORIGIN_ARGS=(--from-scratch)
    else
        if [ -z "$START_FROM" ]; then
            START_FROM="$(latest_solo_best)"
        fi
        [ -n "$START_FROM" ] && [ -f "$START_FROM" ] || die "start_from introuvable.
Copie le best_model solo depuis ta machine locale:
  rsync -avR agent/runs/solo_<timestamp>/score_delta_solo/best_model.zip $REMOTE_HOST:~/tres_fute/"
        ORIGIN="$START_FROM"
        ORIGIN_ARGS=(--start-from "$START_FROM")
    fi

    regenerate_train_script

    if [ -z "$OUTPUT_DIR" ]; then
        OUTPUT_DIR="$RUNS/shaped_$(date -u +%Y%m%d_%H%M%S)"
    fi
    mkdir -p "$OUTPUT_DIR"
    printf '%s\n' "$OUTPUT_DIR" > "$LAST_FILE"
    ln -sfn "$OUTPUT_DIR" "$RUNS/shaped_latest"
    : > "$OUTPUT_DIR/pids"

    IFS=',' read -r -a MODE_ARR <<< "$MODES"
    local mode log
    for mode in "${MODE_ARR[@]}"; do
        log="$OUTPUT_DIR/training_${mode}.log"
        PYTHONPATH="$AGENT_DIR:$BACKEND_DIR" nohup "$PY" -u "$TRAIN_SCRIPT" \
            "${ORIGIN_ARGS[@]}" \
            --checkpoint "$CHECKPOINT" \
            --output-dir "$OUTPUT_DIR" \
            --timesteps "$TIMESTEPS" \
            --n-envs "$N_ENVS" \
            --n-steps "$N_STEPS" \
            --batch-size "$BATCH_SIZE" \
            --n-epochs "$N_EPOCHS" \
            --learning-rate "$LEARNING_RATE" \
            --ent-coef "$ENT_COEF" \
            --gamma "$GAMMA" \
            --alpha "$ALPHA" \
            --beta "$BETA" \
            --phi-scale "$PHI_SCALE" \
            --seed "$SEED" \
            --eval-seed "$EVAL_SEED" \
            --eval-episodes "$EVAL_EPISODES" \
            --eval-every "$EVAL_EVERY" \
            --checkpoint-every "$CHECKPOINT_EVERY" \
            --device "$DEVICE" \
            --torch-threads "$TORCH_THREADS" \
            --modes "$mode" \
            > "$log" 2>&1 < /dev/null &
        echo "$mode $!" >> "$OUTPUT_DIR/pids"
        echo "[$mode] PID $! -> $log"
    done

    if [ "$WITH_TENSORBOARD" = 1 ]; then
        start_tensorboard "$OUTPUT_DIR" "$TB_HOST" "$TB_PORT"
    fi

    cat <<EOF

Sortie          : $OUTPUT_DIR
Start origin    : $ORIGIN
Adversaire      : $CHECKPOINT
Suivi           : $0 status
Logs            : $0 logs

TensorBoard (tunnel SSH depuis ta machine locale) :
  ssh -N -L $TUNNEL_PORT:127.0.0.1:$TB_PORT $REMOTE_HOST
  puis ouvrir http://localhost:$TUNNEL_PORT
EOF
}

read_pids() {
    local out="$1"
    [ -f "$out/pids" ] || return 0
    cat "$out/pids"
}

cmd_status() {
    local out
    out="$(resolve_out)"
    [ -n "$out" ] && [ -d "$out" ] || die "aucun run trouvé (utilise --output-dir ou lance 'start')"
    echo "Run: $out"
    echo
    printf '%-12s %-8s %-8s %s\n' "PROCESS" "PID" "STATE" "LABEL"
    local name pid
    while read -r name pid; do
        [ -n "${pid:-}" ] || continue
        if kill -0 "$pid" 2>/dev/null; then
            printf '%-12s %-8s %-8s %s\n' "$name" "$pid" "RUNNING" ""
        else
            printf '%-12s %-8s %-8s %s\n' "$name" "$pid" "stopped" ""
        fi
    done < <(read_pids "$out")
    echo
    "$PY" - "$out" <<'PY' 2>/dev/null || true
import json
import pathlib
import sys

out = pathlib.Path(sys.argv[1])
print(f"{'run':<10} {'win':>7} {'draw':>7} {'score':>7} {'opp':>7} {'fox':>6} {'min_zone':>9}")
for mode in ("min_zone", "pbrs", "variance"):
    p = out / f"run_{mode}" / "best_metrics.json"
    if not p.exists():
        print(f"{mode:<10} {'-':>7} {'-':>7} {'-':>7} {'-':>7} {'-':>6} {'-':>9}")
        continue
    m = json.loads(p.read_text())
    print(f"{mode:<10} {m['win_rate']*100:>6.1f}% {m['draw_rate']*100:>6.1f}% "
          f"{m['mean_score_agent']:>7.1f} {m['mean_score_opponent']:>7.1f} "
          f"{m['mean_fox_agent']:>6.2f} {m['mean_min_zone_agent']:>9.1f}")
PY
}

cmd_logs() {
    local out
    out="$(resolve_out)"
    [ -n "$out" ] && [ -d "$out" ] || die "aucun run trouvé"
    tail -n 20 -f "$out"/training_*.log
}

cmd_stop() {
    local all=0
    while [ $# -gt 0 ]; do
        case "$1" in
            --output-dir) OUTPUT_DIR="$2"; shift 2;;
            --all) all=1; shift;;
            -h|--help) usage; exit 0;;
            *) die "option inconnue pour stop: $1";;
        esac
    done
    local out
    out="$(resolve_out)"
    [ -n "$out" ] && [ -d "$out" ] || die "aucun run trouvé"
    local name pid
    while read -r name pid; do
        [ -n "${pid:-}" ] || continue
        if [ "$name" = "tensorboard" ] && [ "$all" != 1 ]; then
            continue
        fi
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            echo "arrêté: $name ($pid)"
        fi
    done < <(read_pids "$out")
    if [ "$all" = 1 ]; then
        rm -f "$out/pids"
    fi
}

cmd_tensorboard() {
    local out
    while [ $# -gt 0 ]; do
        case "$1" in
            --output-dir) OUTPUT_DIR="$2"; shift 2;;
            --host) TB_HOST="$2"; shift 2;;
            --port) TB_PORT="$2"; shift 2;;
            -h|--help) usage; exit 0;;
            *) die "option inconnue pour tensorboard: $1";;
        esac
    done
    out="$(resolve_out)"
    [ -n "$out" ] && [ -d "$out" ] || die "aucun run trouvé"
    start_tensorboard "$out" "$TB_HOST" "$TB_PORT"
    echo "ssh -N -L $TUNNEL_PORT:127.0.0.1:$TB_PORT $REMOTE_HOST"
    echo "puis http://localhost:$TUNNEL_PORT"
}

cmd_replays() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --output-dir) OUTPUT_DIR="$2"; shift 2;;
            --seed) REPLAY_SEED="$2"; shift 2;;
            -h|--help) usage; exit 0;;
            *) die "option inconnue pour replays: $1";;
        esac
    done
    require_venv
    local out
    out="$(resolve_out)"
    [ -n "$out" ] && [ -d "$out" ] || die "aucun run trouvé"
    local mode best
    for mode in min_zone pbrs variance; do
        best="$out/run_${mode}/best_model.zip"
        if [ ! -f "$best" ]; then
            echo "[$mode] best_model.zip absent, ignoré"
            continue
        fi
        "$PY" "$AGENT_DIR/rl_env_2/watch_best_model.py" --model "$best" --seed "$REPLAY_SEED"
    done
    echo "Replays dans $out/replays (servis par GET /replays)."
}

main() {
    local cmd="${1:-help}"
    shift || true
    case "$cmd" in
        install) cmd_install "$@";;
        start) cmd_start "$@";;
        status) cmd_status "$@";;
        logs) cmd_logs "$@";;
        stop) cmd_stop "$@";;
        tensorboard) cmd_tensorboard "$@";;
        replays) cmd_replays "$@";;
        help|-h|--help) usage;;
        *) die "commande inconnue: $cmd (voir '$0 help')";;
    esac
}

main "$@"
