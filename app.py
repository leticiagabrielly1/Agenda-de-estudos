from pathlib import Path
import sqlite3
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, flash
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "agenda-local-desenvolvimento"
)

BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "agenda.db"


def conectar():
    conexao = sqlite3.connect(DATABASE)
    conexao.row_factory = sqlite3.Row
    return conexao


def iniciar_banco():
    with conectar() as conexao:
        conexao.execute("""
            CREATE TABLE IF NOT EXISTS tarefas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                materia TEXT NOT NULL,
                descricao TEXT NOT NULL DEFAULT '',
                prazo TEXT NOT NULL,
                prioridade TEXT NOT NULL DEFAULT 'Média',
                concluida INTEGER NOT NULL DEFAULT 0,
                criada_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


@app.template_filter("data_br")
def data_br(valor):
    return date.fromisoformat(valor).strftime("%d/%m/%Y")


@app.route("/")
def index():
    busca = request.args.get("busca", "").strip()
    filtro = request.args.get("filtro", "todas")
    hoje = date.today().isoformat()

    consulta = "SELECT * FROM tarefas WHERE 1 = 1"
    parametros = []

    if busca:
        consulta += " AND (titulo LIKE ? OR materia LIKE ?)"
        parametros.extend([f"%{busca}%", f"%{busca}%"])

    if filtro == "pendentes":
        consulta += " AND concluida = 0"
    elif filtro == "concluidas":
        consulta += " AND concluida = 1"
    elif filtro == "atrasadas":
        consulta += " AND concluida = 0 AND prazo < ?"
        parametros.append(hoje)
    else:
        filtro = "todas"

    consulta += """
        ORDER BY concluida ASC,
                 prazo ASC,
                 CASE prioridade
                     WHEN 'Alta' THEN 1
                     WHEN 'Média' THEN 2
                     ELSE 3
                 END,
                 id DESC
    """

    with conectar() as conexao:
        tarefas = conexao.execute(consulta, parametros).fetchall()

        resumo = conexao.execute("""
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(concluida), 0) AS concluidas,
                COALESCE(SUM(
                    CASE WHEN concluida = 0 AND prazo < ?
                    THEN 1 ELSE 0 END
                ), 0) AS atrasadas
            FROM tarefas
        """, (hoje,)).fetchone()

        materias = conexao.execute("""
            SELECT DISTINCT materia
            FROM tarefas
            ORDER BY materia COLLATE NOCASE
        """).fetchall()

    total = resumo["total"]
    concluidas = resumo["concluidas"]
    progresso = round(concluidas / total * 100) if total else 0

    return render_template(
        "index.html",
        tarefas=tarefas,
        materias=materias,
        total=total,
        concluidas=concluidas,
        pendentes=total - concluidas,
        atrasadas=resumo["atrasadas"],
        progresso=progresso,
        hoje=hoje,
        busca=busca,
        filtro=filtro
    )


@app.route("/adicionar", methods=["POST"])
def adicionar():
    titulo = request.form.get("titulo", "").strip()
    materia = request.form.get("materia", "").strip()
    descricao = request.form.get("descricao", "").strip()
    prazo = request.form.get("prazo", "").strip()
    prioridade = request.form.get("prioridade", "Média")

    if not titulo or not materia or not prazo:
        flash("Preencha o título, a matéria e o prazo.", "erro")
        return redirect(url_for("index"))

    if len(titulo) > 120 or len(materia) > 60 or len(descricao) > 1000:
        flash("Um dos campos ultrapassou o limite de caracteres.", "erro")
        return redirect(url_for("index"))

    try:
        prazo = date.fromisoformat(prazo).isoformat()
    except ValueError:
        flash("Informe uma data válida.", "erro")
        return redirect(url_for("index"))

    if prioridade not in ["Baixa", "Média", "Alta"]:
        flash("Selecione uma prioridade válida.", "erro")
        return redirect(url_for("index"))

    with conectar() as conexao:
        conexao.execute("""
            INSERT INTO tarefas (
                titulo, materia, descricao, prazo, prioridade
            )
            VALUES (?, ?, ?, ?, ?)
        """, (titulo, materia, descricao, prazo, prioridade))

    flash("Tarefa cadastrada!", "sucesso")
    return redirect(url_for("index"))


@app.route("/alternar/<int:tarefa_id>", methods=["POST"])
def alternar(tarefa_id):
    with conectar() as conexao:
        resultado = conexao.execute("""
            UPDATE tarefas
            SET concluida = 1 - concluida
            WHERE id = ?
        """, (tarefa_id,))

    if resultado.rowcount:
        flash("Status da tarefa atualizado.", "sucesso")
    else:
        flash("Tarefa não encontrada.", "erro")

    return redirect(url_for("index"))


@app.route("/excluir/<int:tarefa_id>", methods=["POST"])
def excluir(tarefa_id):
    with conectar() as conexao:
        resultado = conexao.execute(
            "DELETE FROM tarefas WHERE id = ?",
            (tarefa_id,)
        )

    if resultado.rowcount:
        flash("Tarefa excluída.", "sucesso")
    else:
        flash("Tarefa não encontrada.", "erro")

    return redirect(url_for("index"))


iniciar_banco()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)