"""
Tam teşekküllü bir Pomodoro sayacı.

Komutlar:
- start: Pomodoro döngüsünü başlatır ve çalışma/break sürelerini yönetir.
- status: Kaydedilen istatistikleri gösterir.
- reset: Yerel durumu sıfırlar.

Program, çalışma ve mola sürelerini özelleştirmeyi, belirli sayıda
Pomodoro çalıştırmayı, uzun mola sıklığını ayarlamayı ve ilerlemeyi
"~/.pomodoro_state.json" dosyasına kaydetmeyi destekler.
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

STATE_PATH = Path.home() / ".pomodoro_state.json"


@dataclass
class PomodoroState:
    total_pomodoros: int = 0
    total_short_breaks: int = 0
    total_long_breaks: int = 0
    last_session: Optional[str] = None
    config: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "total_pomodoros": self.total_pomodoros,
            "total_short_breaks": self.total_short_breaks,
            "total_long_breaks": self.total_long_breaks,
            "last_session": self.last_session,
            "config": self.config,
        }

    @classmethod
    def from_file(cls, path: Path) -> "PomodoroState":
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            return cls()
        return cls(
            total_pomodoros=int(data.get("total_pomodoros", 0)),
            total_short_breaks=int(data.get("total_short_breaks", 0)),
            total_long_breaks=int(data.get("total_long_breaks", 0)),
            last_session=data.get("last_session"),
            config={k: int(v) for k, v in data.get("config", {}).items()},
        )

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))


def format_duration(seconds: int) -> str:
    minutes, secs = divmod(seconds, 60)
    return f"{minutes:02d}:{secs:02d}"


def countdown(seconds: int, label: str) -> None:
    print(f"\n{label} başladı! {format_duration(seconds)}")
    start = time.monotonic()
    remaining = seconds
    try:
        while remaining > 0:
            mins, secs = divmod(remaining, 60)
            sys.stdout.write(f"\rKalan süre: {mins:02d}:{secs:02d}")
            sys.stdout.flush()
            time.sleep(1)
            elapsed = int(time.monotonic() - start)
            remaining = max(seconds - elapsed, 0)
    except KeyboardInterrupt:
        sys.stdout.write("\nİptal edildi.\n")
        sys.stdout.flush()
        raise
    sys.stdout.write("\rSüre tamamlandı!          \n")
    sys.stdout.flush()


def run_cycle(
    work_duration: int,
    short_break: int,
    long_break: int,
    long_break_every: int,
    sessions: int,
    auto_continue: bool,
    state: PomodoroState,
) -> None:
    completed = 0

    def handle_interrupt(signum, frame):  # type: ignore[unused-argument]
        print("\nOturum sonlandırıldı. Şu ana kadar tamamlanan Pomodoro sayısı:", completed)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_interrupt)

    for index in range(1, sessions + 1):
        countdown(work_duration, f"Pomodoro {index}")
        completed += 1
        state.total_pomodoros += 1
        state.last_session = datetime.now().isoformat(timespec="seconds")
        state.save(STATE_PATH)

        if index == sessions:
            print("Tüm Pomodoro oturumları tamamlandı!")
            break

        if index % long_break_every == 0:
            state.total_long_breaks += 1
            state.save(STATE_PATH)
            countdown(long_break, "Uzun mola")
        else:
            state.total_short_breaks += 1
            state.save(STATE_PATH)
            countdown(short_break, "Kısa mola")

        if not auto_continue:
            proceed = input("Sonraki Pomodoro için Enter'a basın (çıkmak için q): ")
            if proceed.lower().strip() == "q":
                print("Oturum sonlandırıldı.")
                break


def command_start(args: argparse.Namespace) -> None:
    state = PomodoroState.from_file(STATE_PATH)
    config = {
        "work_duration": args.work * 60,
        "short_break": args.short_break * 60,
        "long_break": args.long_break * 60,
        "long_break_every": args.long_break_every,
    }
    state.config = config
    state.save(STATE_PATH)

    print(
        "Başlatılıyor: "
        f"{args.work} dk çalışma, {args.short_break} dk kısa mola, "
        f"{args.long_break} dk uzun mola (her {args.long_break_every}. Pomodoro'dan sonra)."
    )
    run_cycle(
        work_duration=config["work_duration"],
        short_break=config["short_break"],
        long_break=config["long_break"],
        long_break_every=config["long_break_every"],
        sessions=args.sessions,
        auto_continue=args.auto_continue,
        state=state,
    )


def command_status(args: argparse.Namespace) -> None:
    state = PomodoroState.from_file(STATE_PATH)
    config = state.config or {}
    print("Kaydedilen istatistikler:")
    print(f"  Toplam Pomodoro: {state.total_pomodoros}")
    print(f"  Kısa molalar: {state.total_short_breaks}")
    print(f"  Uzun molalar: {state.total_long_breaks}")
    print(f"  Son oturum: {state.last_session or 'Henüz kaydedilmedi'}")
    if config:
        print("  Son kullanılan ayarlar:")
        print(
            f"    Çalışma: {config.get('work_duration', 0) // 60} dk, "
            f"Kısa mola: {config.get('short_break', 0) // 60} dk, "
            f"Uzun mola: {config.get('long_break', 0) // 60} dk, "
            f"Uzun mola sıklığı: {config.get('long_break_every', 0)}"
        )
    else:
        print("  Ayar kaydı bulunamadı.")


def command_reset(args: argparse.Namespace) -> None:
    if STATE_PATH.exists():
        STATE_PATH.unlink()
        print("Kayıtlı durum dosyası silindi.")
    else:
        print("Silinecek bir durum dosyası bulunamadı.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Pomodoro sayaç aracı")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Pomodoro döngüsünü başlat")
    start.add_argument("--work", type=int, default=25, help="Çalışma süresi (dakika)")
    start.add_argument("--short-break", dest="short_break", type=int, default=5, help="Kısa mola süresi (dakika)")
    start.add_argument("--long-break", dest="long_break", type=int, default=15, help="Uzun mola süresi (dakika)")
    start.add_argument(
        "--long-break-every",
        dest="long_break_every",
        type=int,
        default=4,
        help="Kaç Pomodoro'da bir uzun mola verileceği",
    )
    start.add_argument("--sessions", type=int, default=4, help="Toplam Pomodoro sayısı")
    start.add_argument(
        "--auto-continue",
        action="store_true",
        help="Molalar sonrası otomatik olarak sonraki Pomodoro'ya geç",
    )
    start.set_defaults(func=command_start)

    status = subparsers.add_parser("status", help="Kaydedilen istatistikleri göster")
    status.set_defaults(func=command_status)

    reset = subparsers.add_parser("reset", help="Kayıtlı durum dosyasını sil")
    reset.set_defaults(func=command_reset)

    return parser


def main(argv: Optional[list[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
