# 心臓MRI TI Scout・LGEシミュレータ

ブラウザ内で計算する静的Webアプリです。3 T・ガドビスト分割投与モデルを用いて信号曲線、左室短軸像、TI scout・PSIRの推定null TI、仮想LGE病変を表示します。

公開URL：https://radiotec-maker.github.io/cardiac-ti-scout-simulator/

設定体重に応じた投与量を表示します。2回目注入開始は1回目注入開始から1分後です。撮像時刻は2回目注入開始からの経過時間です。

## 開発と確認

アプリ本体：`web/`

ローカル確認：`py -m http.server 8080 --directory web` を実行し、http://localhost:8080/ を開きます。公開アプリの動作にPythonは不要です。

テスト：`node --test web/tests/model.test.mjs`

GitHub PagesのSourceはGitHub Actionsです。公開設定は `.github/workflows/pages.yml` にあります。

旧Streamlit版はGit履歴のコミット `668ddd2` から復元できます。

教育・施設内検討用の簡略モデルです。患者個別の投与量や最適TIを決定するものではありません。
