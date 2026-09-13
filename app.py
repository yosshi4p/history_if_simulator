from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import openai
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_sqlalchemy import SQLAlchemy
from openai import OpenAI
from sqlalchemy.exc import SQLAlchemyError

from prompt import build_worldline_prompt, SYSTEM_INSTRUCTIONS


# =========================================================
# 基本設定
# =========================================================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

# flashメッセージを使用するためのSECRET_KEY
# Render公開時には環境変数SECRET_KEYを設定する想定
app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "history-if-simulator-development-key"
)


# =========================================================
# データベース設定
# =========================================================

# DATABASE_URLが設定されていなければSQLiteを使用
sqlite_path = os.path.join(
    BASE_DIR,
    "history_if.db"
).replace("\\", "/")

database_url = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{sqlite_path}"
)

# 一部サービスでは postgres:// 形式になる場合があるため変換
if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# =========================================================
# OpenAI設定
# =========================================================

OPENAI_MODEL = (
    os.getenv("OPENAI_MODEL", "gpt-5.6-terra").strip()
    or "gpt-5.6-terra"
)


# =========================================================
# 日本時間
# =========================================================

JST = ZoneInfo("Asia/Tokyo")


def jst_now() -> datetime:
    """
    SQLiteでも扱いやすいように、
    日本時間のnaive datetimeとして保存する。
    """
    return datetime.now(JST).replace(tzinfo=None)


# =========================================================
# データベースモデル
# =========================================================

class Worldline(db.Model):
    """
    保存された世界線
    """

    __tablename__ = "worldlines"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    world_id = db.Column(
        db.String(30),
        unique=True,
        index=True,
        nullable=True
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    branch_point = db.Column(
        db.Text,
        nullable=False
    )

    output_format = db.Column(
        db.String(50),
        nullable=False
    )

    body = db.Column(
        db.Text,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=jst_now
    )

    def __repr__(self) -> str:
        return f"<Worldline {self.world_id}>"


# =========================================================
# 初期データ
# =========================================================

PRESET_BRANCHES = [
    {
        "title": "本能寺の変",
        "branch": "本能寺の変が起きなかったら",
        "meta": "1582年 / 日本",
    },
    {
        "title": "関ヶ原の戦い",
        "branch": "関ヶ原の戦いで西軍が勝っていたら",
        "meta": "1600年 / 日本",
    },
    {
        "title": "鎖国",
        "branch": "日本が鎖国しなかったら",
        "meta": "17世紀 / 日本",
    },
    {
        "title": "坂本龍馬",
        "branch": "坂本龍馬が暗殺されなかったら",
        "meta": "1867年 / 日本",
    },
    {
        "title": "アポロ11号",
        "branch": "アポロ11号が月面着陸に失敗していたら",
        "meta": "1969年 / アメリカ",
    },
    {
        "title": "ソビエト連邦",
        "branch": "ソ連が崩壊しなかったら",
        "meta": "1991年 / 世界",
    },
]


OUTPUT_FORMATS = [
    "年表",
    "ニュース記事",
    "映画のあらすじ",
    "歴史教科書",
    "SF短編",
]


# =========================================================
# 補助関数
# =========================================================

def create_title(branch_point: str) -> str:
    """
    分岐点から保存用タイトルを作成する。
    """

    text = " ".join(branch_point.split())

    if len(text) > 70:
        text = text[:70] + "…"

    return f"もしも、{text}"


def create_openai_client() -> OpenAI:
    """
    OpenAIクライアントを作成する。

    APIキーは必ず環境変数OPENAI_API_KEYから取得する。
    """

    api_key = os.getenv("OPENAI_API_KEY", "").strip()

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY が設定されていません。"
        )

    return OpenAI(
        api_key=api_key,
        timeout=75.0,
        max_retries=1,
    )


def generate_worldline(
    branch_point: str,
    output_format: str
) -> str:
    """
    OpenAI APIを呼び出して世界線を生成する。
    """

    client = create_openai_client()

    user_prompt = build_worldline_prompt(
        branch_point=branch_point,
        output_format=output_format,
    )

    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=SYSTEM_INSTRUCTIONS,
        input=user_prompt,
        max_output_tokens=3500,
    )

    text = response.output_text

    if not text:
        raise RuntimeError(
            "OpenAI APIから本文が返されませんでした。"
        )

    return text.strip()


def render_top():
    """
    トップページを表示する際の共通処理。
    """

    return render_template(
        "index.html",
        preset_branches=PRESET_BRANCHES,
        output_formats=OUTPUT_FORMATS,
    )


# =========================================================
# トップページ
# =========================================================

@app.route("/", methods=["GET"])
def index():
    return render_top()


# =========================================================
# 世界線生成
# =========================================================

@app.route("/generate", methods=["POST"])
def generate():
    """
    フォームから受け取った分岐点を使って
    AIに世界線を生成させる。
    """

    selected_branch = request.form.get(
        "branch_point",
        ""
    ).strip()

    custom_branch = request.form.get(
        "custom_branch",
        ""
    ).strip()

    output_format = request.form.get(
        "output_format",
        ""
    ).strip()

    # 自由入力があれば自由入力を優先
    branch_point = custom_branch or selected_branch

    # -----------------------------------------
    # 入力チェック
    # -----------------------------------------

    if not branch_point:
        flash(
            "歴史の分岐点を選択するか、自由入力してください。",
            "error",
        )
        return redirect(url_for("index"))

    if output_format not in OUTPUT_FORMATS:
        flash(
            "出力形式を選択してください。",
            "error",
        )
        return redirect(url_for("index"))

    title = create_title(branch_point)

    # -----------------------------------------
    # OpenAI API呼び出し
    # -----------------------------------------

    try:
        body = generate_worldline(
            branch_point=branch_point,
            output_format=output_format,
        )

    # APIキー未設定
    except ValueError:
        app.logger.exception(
            "OPENAI_API_KEY is not configured."
        )

        flash(
            "OpenAI APIキーが設定されていません。"
            "管理者にご確認ください。",
            "error",
        )

        return redirect(url_for("index"))

    # API利用上限・レート制限
    except openai.RateLimitError:
        app.logger.exception(
            "OpenAI rate limit or quota error."
        )

        flash(
            "現在、AIの利用上限に達している可能性があります。"
            "時間をおいて、もう一度お試しください。",
            "error",
        )

        return redirect(url_for("index"))

    # APIキーが不正
    except openai.AuthenticationError:
        app.logger.exception(
            "OpenAI authentication error."
        )

        flash(
            "OpenAI APIの認証に失敗しました。"
            "APIキーをご確認ください。",
            "error",
        )

        return redirect(url_for("index"))

    # タイムアウト
    except openai.APITimeoutError:
        app.logger.exception(
            "OpenAI request timed out."
        )

        flash(
            "世界線の観測に時間がかかりすぎました。"
            "もう一度お試しください。",
            "error",
        )

        return redirect(url_for("index"))

    # 通信エラー
    except openai.APIConnectionError:
        app.logger.exception(
            "Could not connect to OpenAI API."
        )

        flash(
            "AIとの通信に失敗しました。"
            "しばらくしてから、もう一度お試しください。",
            "error",
        )

        return redirect(url_for("index"))

    # OpenAI APIからその他のエラー
    except openai.APIStatusError as exc:
        app.logger.exception(
            "OpenAI API status error: %s",
            exc.status_code,
        )

        flash(
            "世界線の生成に失敗しました。"
            "もう一度お試しください。",
            "error",
        )

        return redirect(url_for("index"))

    # OpenAI SDK全般
    except openai.APIError:
        app.logger.exception(
            "Unexpected OpenAI API error."
        )

        flash(
            "世界線の生成に失敗しました。"
            "もう一度お試しください。",
            "error",
        )

        return redirect(url_for("index"))

    # 予期しないエラー
    except Exception:
        app.logger.exception(
            "Unexpected error while generating worldline."
        )

        flash(
            "世界線の生成中に予期しないエラーが発生しました。"
            "もう一度お試しください。",
            "error",
        )

        return redirect(url_for("index"))

    # -----------------------------------------
    # 生成成功
    # -----------------------------------------

    return render_template(
        "result.html",
        title=title,
        branch_point=branch_point,
        output_format=output_format,
        body=body,
        world_id=None,
        saved=False,
    )


# =========================================================
# 世界線を保存
# =========================================================

@app.route("/save", methods=["POST"])
def save_worldline():
    """
    AI生成結果をSQLiteへ保存する。
    """

    title = request.form.get(
        "title",
        ""
    ).strip()

    branch_point = request.form.get(
        "branch_point",
        ""
    ).strip()

    output_format = request.form.get(
        "output_format",
        ""
    ).strip()

    body = request.form.get(
        "body",
        ""
    ).strip()

    # -----------------------------------------
    # 入力チェック
    # -----------------------------------------

    if not all(
        [
            title,
            branch_point,
            output_format,
            body,
        ]
    ):
        flash(
            "保存する世界線の情報が不足しています。",
            "error",
        )
        return redirect(url_for("index"))

    if output_format not in OUTPUT_FORMATS:
        flash(
            "不正な出力形式です。",
            "error",
        )
        return redirect(url_for("index"))

    # -----------------------------------------
    # DB保存
    # -----------------------------------------

    try:
        worldline = Worldline(
            title=title[:200],
            branch_point=branch_point,
            output_format=output_format,
            body=body,
            created_at=jst_now(),
        )

        db.session.add(worldline)

        # ここでIDだけ先に確定させる
        db.session.flush()

        # WORLD-001形式のIDを作成
        worldline.world_id = (
            f"WORLD-{worldline.id:03d}"
        )

        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()

        app.logger.exception(
            "Database error while saving worldline."
        )

        flash(
            "世界線の保存に失敗しました。"
            "もう一度お試しください。",
            "error",
        )

        return render_template(
            "result.html",
            title=title,
            branch_point=branch_point,
            output_format=output_format,
            body=body,
            world_id=None,
            saved=False,
        )

    flash(
        f"{worldline.world_id} を保存しました。",
        "success",
    )

    return redirect(
        url_for(
            "worldline_detail",
            world_id=worldline.world_id,
        )
    )


# =========================================================
# 保存した世界線一覧
# =========================================================

@app.route("/collection", methods=["GET"])
def collection():
    """
    保存済みの世界線を新しい順に一覧表示する。
    """

    worldlines = (
        Worldline.query
        .order_by(Worldline.created_at.desc())
        .all()
    )

    return render_template(
        "collection.html",
        worldlines=worldlines,
    )


# =========================================================
# 世界線詳細
# =========================================================

@app.route(
    "/worldline/<string:world_id>",
    methods=["GET"]
)
def worldline_detail(world_id: str):
    """
    保存済み世界線を1件表示する。
    """

    worldline = Worldline.query.filter_by(
        world_id=world_id
    ).first_or_404()

    return render_template(
        "detail.html",
        worldline=worldline,
    )


# =========================================================
# 世界線削除
# =========================================================

@app.route(
    "/worldline/<string:world_id>/delete",
    methods=["POST"]
)
def delete_worldline(world_id: str):
    """
    保存した世界線を削除する。
    """

    worldline = Worldline.query.filter_by(
        world_id=world_id
    ).first_or_404()

    try:
        db.session.delete(worldline)
        db.session.commit()

    except SQLAlchemyError:
        db.session.rollback()

        app.logger.exception(
            "Database error while deleting worldline."
        )

        flash(
            "世界線の削除に失敗しました。",
            "error",
        )

        return redirect(
            url_for(
                "worldline_detail",
                world_id=world_id,
            )
        )

    flash(
        f"{world_id} を削除しました。",
        "success",
    )

    return redirect(
        url_for("collection")
    )


# =========================================================
# Renderなどの稼働確認用
# =========================================================

@app.route("/health", methods=["GET"])
def health():
    return {
        "status": "ok",
        "model": OPENAI_MODEL,
    }, 200


# =========================================================
# DB作成
# =========================================================

with app.app_context():
    db.create_all()


# =========================================================
# ローカル起動
# =========================================================

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
    )