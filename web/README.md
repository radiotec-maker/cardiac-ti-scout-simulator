# 静的Web版

既存のStreamlit版を変更せず並行運用する、GitHub Pages向けの静的Web版です。

ローカル確認：`py -m http.server 8080 --directory web`

テスト：`node --test web/tests/model.test.mjs`

GitHub Pagesでは Settings → Pages → Source で **GitHub Actions** を選択します。
