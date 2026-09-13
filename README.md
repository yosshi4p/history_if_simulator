# 歴史ifシミュレーター：PCでの起動手順

第1回のapp.pyに、画面とAIへの指示を合わせた版です。
添付されたapp.pyの内容は変更していません。
今回のZIPには、修正したHTML4枚、CSS、prompt.py、requirements.txt、
この説明書、.gitignoreを含めています。APIキーやデータベースは含みません。

## 1. ファイルを配置する

ZIPを右クリックして「すべて展開」を選びます。
展開先のhistory_if_simulatorフォルダ内にあるファイルとフォルダを、
デスクトップに作った既存のhistory_if_simulatorへコピーしてください。
HTMLとstyle.cssは今回のものに置き換えます。既存のフォルダ自体を削除する必要はありません。

| ファイル | 置く場所 |
| --- | --- |
| app.py | history_if_simulatorの直下 |
| prompt.py | app.pyと同じ場所 |
| requirements.txt | app.pyと同じ場所 |
| README.md、.gitignore | app.pyと同じ場所 |
| index.html、result.html、collection.html、detail.html | templatesの中 |
| style.css | staticの中 |

app.pyの中にtemplatesやstaticを入れるのではなく、app.py、templates、staticが横に並ぶ配置です。
フォルダの中に同名のhistory_if_simulatorフォルダをもう一つ入れないようにしてください。

## 2. VS Codeでアプリのフォルダを開く

「ファイル」→「フォルダーを開く」で、デスクトップのhistory_if_simulatorを開きます。
「ターミナル」→「新しいターミナル」を選び、PowerShellで下記を1行ずつ実行します。
前の行でエラーが出た場合は、そこで止めてエラー文を確認してください。

```powershell
cd "C:\Users\Owner\OneDrive\Desktop\history_if_simulator"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Python 3.10以降を想定しています。pyが見つからない場合は、
まず `python --version` を確認し、利用可能なら2行目を `python -m venv .venv` にします。
仮想環境の有効化コマンドは不要です。.venv内のPythonを直接指定するためです。

## 3. アプリを起動する

最初の確認では、このアプリ用のSQLiteファイルを使います。
別のアプリ用DATABASE_URLがPCに設定されていても使わないよう、
今開いているPowerShell内だけ、その値を解除してから起動します。
Windowsに保存された環境変数や、ほかのアプリの設定は変更しません。

```powershell
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe app.py
```

ターミナルに `Running on http://127.0.0.1:5000` と表示されたら、
ブラウザーで [http://127.0.0.1:5000/](http://127.0.0.1:5000/) を開きます。
このターミナルは、アプリを使っている間は開いたままにしてください。
終了する場合はターミナルでCtrl+Cを押します。

HTMLファイルをダブルクリックしても、Flaskのテンプレート処理は動きません。
ブラウザーのアドレス欄がC:/Users/...ではなく、上記URLになっていることを確認してください。
トップページとCSS、保存0件のコレクション表示はAPIキーなしでも確認できます。

## 4. AIで生成する

生成時には、有効なOPENAI_API_KEYが環境変数に設定されている必要があります。
すでにWindowsへ登録済みなら、登録後にVS Codeを開き直すと引き継がれます。
値を表示せず、設定の有無だけ確認する場合は、アプリをCtrl+Cで止めてから実行します。

```powershell
if ($env:OPENAI_API_KEY) { "APIキーは設定済みです" } else { "APIキーは未設定です" }
```

未設定の場合は、Windowsの環境変数にOPENAI_API_KEYを登録してからVS Codeを開き直します。
キーそのものをapp.py、HTML、GitHub、チャットへ貼り付ける必要はありません。
このapp.pyは.envファイルを自動では読み込みません。

設定後は、手順3の2行で起動し、次の流れを確認します。

1. カードまたは自由入力で分岐点を指定する。
2. 「年表」「ニュース記事」「映画のあらすじ」「歴史教科書」「SF短編」から選ぶ。
3. 「もしもの世界線を生成する」を押す。
4. 結果を読んで、「コレクションに保存」を押す。
5. WORLD-001などの番号が付いた詳細画面と、コレクションの一覧を確認する。

生成しただけでは保存されません。保存ボタンを押すと、このフォルダ内の
history_if.dbに保存されます。このファイルを消すと、ローカルで保存した世界線が失われます。

モデルは第1回の既定値gpt-5.6-terraを引き継いでいます。
既存のOPENAI_MODEL環境変数がある場合は、その値が優先されます。
既定のモデルはResponses API対応として[OpenAI公式資料](https://developers.openai.com/api/docs/models/gpt-5.6-terra)で確認しています。
利用可否や残高は、利用するAPIプロジェクトの設定によります。

## 今回合わせた箇所

| 接続部分 | app.pyに合わせた値・動作 |
| --- | --- |
| 自由入力欄 | custom_branchを送信 |
| 出力形式 | OUTPUT_FORMATSの日本語5種類を表示・送信 |
| 生成結果の本文 | bodyを表示 |
| 保存 | title、branch_point、output_format、bodyを/saveに送信 |
| 一覧 | worldlinesを表示 |
| 詳細 | /worldline/WORLD-001などのURLを使用し、worldline.bodyを表示 |
| 削除 | 詳細の削除欄から、確認後に既存の削除ルートへ送信 |
| 読み込み中 | ブラウザーの「戻る」でも送信ボタンが使用可能 |

## 検証の範囲

同梱のapp.pyとFlaskのテストクライアントを使い、ページ・CSSの配信、
5種類の入力から結果表示、自由入力の優先、保存・一覧・詳細・削除、
APIエラー時の表示、保存失敗後の再試行を確認しています。
OpenAIへの応答はテスト用の通信に置き換えているため、検証で実際のAPI料金は発生していません。
実際のAI生成、よっちんのWindowsでの起動、ブラウザーでの見た目は、PC側で続けて確認してください。

## 公開する前の確認

今回はPCで動作確認するための構成です。Renderへの公開は、この動作確認後に進めます。
このapp.pyにはログインやユーザー別の履歴分離がないため、そのまま公開すると、
保存した世界線の閲覧・保存・削除が全利用者で共通になります。
公開時はその運用でよいか確認し、SECRET_KEY、保存先データベース、
生成回数の制限などを設定してから公開します。
