"""Tira do historico do OpenJarvis as falas da casa captadas antes da palavra "Jarvis".

Nao apaga de vez: antes, copia o banco inteiro e grava os registros removidos em
JSON numa pasta de backup. Para desfazer, basta devolver traces-antes.db.
"""
import json
import pathlib
import sqlite3
import time

HOME = pathlib.Path.home() / ".openjarvis"
ALVOS = {7: "...", 10: "Que bem comemor!", 11: "Sabe?", 12: "Ai, ai!", 13: "Vai vim comer, amor!"}

dest = HOME / "backups" / (time.strftime("%Y%m%d-%H%M%S") + "-historico")
dest.mkdir(parents=True)
con = sqlite3.connect(HOME / "traces.db")
con.row_factory = sqlite3.Row
bk = sqlite3.connect(dest / "traces-antes.db")
con.backup(bk)
bk.close()

linhas = [dict(r) for r in con.execute(
    f"select * from traces where id in ({','.join('?' * len(ALVOS))})", list(ALVOS))]
assert len(linhas) == len(ALVOS), "registros nao batem"
for r in linhas:
    assert r["query"] == ALVOS[r["id"]], f"id {r['id']} mudou: {r['query']!r}"
ids = [r["trace_id"] for r in linhas]
passos = [dict(r) for r in con.execute(
    f"select * from trace_steps where trace_id in ({','.join('?' * len(ids))})", ids)]
(dest / "removidos.json").write_text(json.dumps({"traces": linhas, "trace_steps": passos},
                                                ensure_ascii=False, indent=2), encoding="utf-8")

with con:
    for r in linhas:          # o indice de busca (FTS) so tem gatilho de insercao
        con.execute("insert into traces_fts(traces_fts, rowid, trace_id, query, result, agent) "
                    "values('delete', ?, ?, ?, ?, ?)",
                    (r["id"], r["trace_id"], r["query"], r["result"], r["agent"]))
    con.execute(f"delete from trace_steps where trace_id in ({','.join('?' * len(ids))})", ids)
    con.execute(f"delete from traces where id in ({','.join('?' * len(ALVOS))})", list(ALVOS))
con.execute("insert into traces_fts(traces_fts) values('integrity-check')")
restantes = con.execute("select count(*) from traces").fetchone()[0]
fts = con.execute("select count(*) from traces_fts where traces_fts match 'comer'").fetchone()[0]
con.close()
print(f"arquivados {len(linhas)} registros e {len(passos)} passos em {dest}")
print(f"restam {restantes} no historico; busca por 'comer' acha {fts}")
