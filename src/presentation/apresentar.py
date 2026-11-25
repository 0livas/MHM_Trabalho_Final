"""Monta um player local para as seções de um render Manim com --save_sections."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCENES = (
    "Abertura", "Fundamentos", "Exatos", "Heuristicas", "Metaheuristicas",
    "Calibracao", "CasoVNS", "Metricas", "Resultados", "Fechamento",
)
BEAT = re.compile(r"^### (\d\d:\d\d) · `([a-z0-9_]+)`$", re.MULTILINE)
DECKS = {
    "completo": dict(file="apresentacao", scenes=SCENES, notes="ROTEIRO.md", seconds=1800, media="mhm",
                     title="MHM — apresentação e resultados", appendix=True),
    "introducao": dict(file="introducao", scenes=("IntroFabrica", "ProblemaMaquinas", "ProblemaSimulacao", "ObjetivosECaminhos"),
                       notes="ROTEIRO_INTRODUCAO.md", seconds=690, media="introducao",
                       title="MHM — introdução e problema", appendix=False),
    # Metodologia: um deck por sessão de trabalho; ver diretrizes/.
    "exato": dict(file="anim_exato", scenes=("ExatoEstados", "ExatoEscada"),
        notes="ROTEIRO_EXATO.md", seconds=180, media="exato", title="MHM — método exato", appendix=False),
    "heuristica": dict(file="anim_heuristica", scenes=("HeuristicaConstrutiva", "HeuristicaOciosidade"),
        notes="ROTEIRO_HEURISTICA.md", seconds=180, media="heuristica", title="MHM — heurística", appendix=False),
    "vns": dict(file="anim_vns", scenes=("VnsPartida", "VnsDescida", "VnsBusca"),
        notes="ROTEIRO_VNS.md", seconds=210, media="vns", title="MHM — VNS/VND", appendix=False),
    "spea2": dict(file="anim_spea2", scenes=("Spea2Arena", "Spea2Operadores", "Spea2Busca"),
        notes="ROTEIRO_SPEA2.md", seconds=210, media="spea2", title="MHM — SPEA2", appendix=False),
    "moead": dict(file="anim_moead", scenes=("MoeadLeque", "MoeadVizinhos", "MoeadBusca"),
        notes="ROTEIRO_MOEAD.md", seconds=180, media="moead", title="MHM — MOEA/D", appendix=False),
    "age": dict(file="anim_age", scenes=("AgeCamadas", "AgeGeometria", "AgeBusca"),
        notes="ROTEIRO_AGE.md", seconds=180, media="age", title="MHM — AGE-MOEA", appendix=False),
    "calibracao": dict(file="anim_calibracao", scenes=("CalibracaoMesa", "CalibracaoTorneio"),
        notes="ROTEIRO_CALIBRACAO.md", seconds=180, media="calibracao", title="MHM — calibração", appendix=False),
}
QUALITIES = {"l": "480p15", "m": "720p30", "h": "1080p60"}


def clock(seconds):
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def relative_url(path, base):
    try:
        return quote(Path(os.path.relpath(path, base)).as_posix(), safe="/.")
    except ValueError:
        return path.as_uri()


def playlist(sections, destination, deck):
    rows = []
    for scene in deck["scenes"]:
        metadata_path = sections / f"{scene}.json"
        entries = json.loads(metadata_path.read_text(encoding="utf-8"))
        for entry in entries:
            clip = sections / entry["video"]
            if not clip.is_file() or float(entry["duration"]) <= 0:
                raise ValueError(f"Seção sem vídeo válido: {clip}")
            rows.append(dict(scene=scene, name=entry["name"], url=relative_url(clip, destination),
                             duration=float(entry["duration"])))
    notes = HERE / deck["notes"]
    cues = BEAT.findall(notes.read_text(encoding="utf-8"))
    if [name for _, name in cues] != [row["name"] for row in rows]:
        raise ValueError("As seções renderizadas precisam ter a mesma ordem e os mesmos nomes que o roteiro.")
    starts = [60 * int(at[:2]) + int(at[3:]) for at, _ in cues]
    if not starts or starts[0] != 0 or starts != sorted(set(starts)) or starts[-1] >= deck["seconds"]:
        raise ValueError("As marcas de início precisam ser crescentes entre 00:00 e o fim do deck.")
    for row, start, end in zip(rows, starts, [*starts[1:], deck["seconds"]]):
        if row["duration"] > end - start:
            raise ValueError(f"A animação de {row['name']} excede o tempo de fala previsto.")
        row.update(start=clock(start), end=clock(end), start_seconds=start)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--deck", choices=DECKS, default="completo", help="Apresentação a montar.")
    parser.add_argument("--render", action="store_true", help="Renderiza o deck completo antes de montar o player.")
    parser.add_argument("--quality", choices=QUALITIES, default="h", help="l: prévia rápida, m: 720p, h: 1080p.")
    parser.add_argument("--media-dir", type=Path, help="Destino dos vídeos e do player.")
    args = parser.parse_args()
    deck = DECKS[args.deck]
    media = (args.media_dir or ROOT / "media" / deck["media"]).resolve()
    if args.render:
        subprocess.run([sys.executable, "-m", "manim", f"-q{args.quality}", "--save_sections", "--media_dir",
                        str(media), "--progress_bar", "none", "-v", "WARNING", str(HERE / f"{deck['file']}.py"), *deck["scenes"]],
                       cwd=ROOT, check=True)
    sections = media / "videos" / deck["file"] / QUALITIES[args.quality] / "sections"
    output = media / "index.html"
    summary = json.loads((HERE / "data" / "results.json").read_text(encoding="utf-8"))
    payload = dict(clips=playlist(sections, output.parent, deck), title=deck["title"],
                   appendix=deck["appendix"], summary=summary,
                   notes=relative_url(HERE / deck["notes"], media),
                   csv=relative_url(HERE / "data" / "metrics_summary.csv", media))
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    template = (HERE / "player.html").read_text(encoding="utf-8")
    output.write_text(template.replace("/*DADOS_DO_DECK*/", serialized), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
