#!/data/data/com.termux/files/usr/bin/bash
# Utilidades compartidas por los vigias TikTok de Termux.

tiktok_lock_pid() {
    local lock_file="$1"
    awk 'NR == 1 {print $1}' "$lock_file" 2>/dev/null || true
}

tiktok_lock_label() {
    local lock_file="$1"
    cut -d' ' -f2- "$lock_file" 2>/dev/null || true
}

tiktok_pid_alive() {
    local pid="$1"
    case "$pid" in
        ''|*[!0-9]*) return 1 ;;
    esac
    kill -0 "$pid" 2>/dev/null
}

tiktok_check_lock() {
    local lock_file="$1"
    local scope="$2"
    local lock_pid=""
    local lock_label=""

    [ -f "$lock_file" ] || return 0
    lock_pid="$(tiktok_lock_pid "$lock_file")"
    lock_label="$(tiktok_lock_label "$lock_file")"

    if tiktok_pid_alive "$lock_pid"; then
        if [ "$lock_pid" != "$$" ]; then
            echo "[LOCK] ${scope}: ya hay un vigia TikTok corriendo (PID ${lock_pid}${lock_label:+, ${lock_label}})."
            echo "[LOCK] Usa PARAR_TIKTOK antes de cambiar de widget o cuenta."
            return 1
        fi
        return 0
    fi

    echo "[LOCK] ${scope}: lock viejo sin proceso vivo, limpiando ${lock_file}."
    rm -f "$lock_file" 2>/dev/null || true
    return 0
}

acquire_tiktok_vigia_locks() {
    local own_lock="$1"
    local widget_name="$2"
    local global_lock="${TIKTOK_GLOBAL_LOCK:-$HOME/vigia_tiktok_global.lock}"
    local stamp=""

    if ! tiktok_check_lock "$global_lock" "global"; then
        return 1
    fi
    if ! tiktok_check_lock "$own_lock" "$widget_name"; then
        return 1
    fi

    stamp="$(date '+%Y-%m-%d_%H:%M:%S' 2>/dev/null || true)"
    printf '%s %s %s\n' "$$" "$widget_name" "$stamp" > "$global_lock"
    printf '%s %s %s\n' "$$" "$widget_name" "$stamp" > "$own_lock"
    return 0
}

release_tiktok_vigia_lock() {
    local lock_file="$1"
    local lock_pid=""

    [ -f "$lock_file" ] || return 0
    lock_pid="$(tiktok_lock_pid "$lock_file")"
    if [ "$lock_pid" = "$$" ]; then
        rm -f "$lock_file" 2>/dev/null || true
    fi
}

release_tiktok_vigia_locks() {
    local own_lock="$1"
    local global_lock="${TIKTOK_GLOBAL_LOCK:-$HOME/vigia_tiktok_global.lock}"

    release_tiktok_vigia_lock "$own_lock"
    release_tiktok_vigia_lock "$global_lock"
}
