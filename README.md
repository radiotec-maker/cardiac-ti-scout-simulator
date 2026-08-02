# 心臓MRI 正常心筋TI–信号強度シミュレータ

3 T心臓MRIにおけるガドビスト分割投与後の正常心筋について、推定T1、null TI、正規化Magnitude TI–信号強度曲線を確認するためのStreamlitアプリです。

本アプリは教育・施設内検討用です。患者個別の造影剤投与量、最適TI、診断または治療方針を決定する目的には使用しないでください。

## 動作環境

- Windows 10またはWindows 11
- Python 3.10以降
- インターネット接続（初回のライブラリインストール時のみ）

以下の手順では、PowerShellを使用します。最初にPowerShellを開き、このプロジェクトのフォルダーへ移動してください。

```powershell
cd C:\path\to\cardiac-ti-scout-simulator
```

`C:\path\to`の部分は、実際にプロジェクトを保存した場所へ置き換えます。

## 1. 仮想環境を作成する

仮想環境を使用すると、このアプリで使うライブラリをほかのPythonプロジェクトから分離できます。プロジェクトフォルダーで次を実行します。

```powershell
py -m venv .venv
```

`py`が見つからない場合は、次を試してください。

```powershell
python -m venv .venv
```

`.venv`というフォルダーが作成されれば成功です。

## 2. 仮想環境を有効化する

```powershell
.\.venv\Scripts\Activate.ps1
```

PowerShellの実行ポリシーにより拒否された場合は、そのPowerShell画面だけ一時的に許可してから、もう一度有効化します。

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

コマンド行の先頭に`(.venv)`と表示されれば有効化されています。以降のコマンドは、仮想環境を有効にしたまま実行してください。

## 3. ライブラリをインストールする

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

初回はStreamlit、NumPy、Pandas、Plotly、pytestなどがダウンロードされます。

## 4. 単体テストを実行する

```powershell
python -m pytest -q
```

最後に`passed`と表示され、`failed`が表示されなければ計算テストは成功です。

## 5. Streamlitアプリを起動する

```powershell
python -m streamlit run app.py
```

通常はWebブラウザーが自動的に開きます。開かない場合は、PowerShellに表示される`Local URL`（通常は`http://localhost:8501`）をブラウザーで開いてください。

終了するときは、PowerShellで`Ctrl+C`を押します。仮想環境を終了する場合は次を実行します。

```powershell
deactivate
```

## 使い方

画面で体重A、体重B、TI scout撮像時刻、正常心筋native T1を入力します。入力を変更すると自動的に再計算され、2つの体重の結果とTI–信号強度曲線が更新されます。

「詳細設定」では文献参照係数、施設校正値、TI表示範囲を変更できます。「初期値に戻す」を押すと、すべての入力が仕様書の初期値へ戻ります。

入力内容と計算結果は保存されません。氏名、患者IDなど、患者を特定できる情報を入力する機能もありません。

## モデルの制限と注意事項

- 文献値および暫定的な施設経験値に基づく簡略モデルです。
- 対象は3 T、ガドビスト、正常心筋です。1.5 T、血液、病変心筋は対象外です。
- 表示濃度はT1から換算した見かけ濃度であり、真の組織濃度ではありません。
- 信号値は正規化された相対値で、実機のDICOM信号値ではありません。
- 実機固有のLook-Locker信号挙動、心拍数、腎機能、心拍出量などは反映していません。
- 患者個別の最適TIや造影剤投与量を決定するものではありません。
- 診断、治療方針の決定、患者個別の臨床判断には使用しないでください。
