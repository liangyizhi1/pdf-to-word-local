# PDF to Word Local

一个注重隐私的离线 PDF 转 Word 工具，提供桌面界面、批量转换、可选公式识别、图片提取与分割，以及结构化质量报告。

> 当前为早期版本。0.3 版的公式 OCR 和图片分割均为可选功能，适合辅助处理和人工复核。

## Windows 使用方法

1. 安装 Python 3.10 或更高版本。
2. 首次使用时双击 `install_windows.bat` 安装本地转换引擎。
3. 双击 `run_app.bat` 启动桌面程序。
4. 添加 PDF、选择输出目录，然后点击 Convert。

文件不会上传，默认使用本地开源 `pdf2docx` 引擎。

## 公式识别

公式 OCR 模型较大，因此不会随基础转换器默认安装。

1. 双击 `install_formula_ocr.bat` 安装一次。
2. 在桌面程序中勾选 **Recognize formula images (experimental)**。
3. 转换后对照原 PDF 检查 Word 文末的公式附录。

识别结果包含页码、原 PDF 边界框、LaTeX、置信度（模型提供时）、识别状态和 Word 渲染方式。Windows 安装了 Microsoft Office 和 `latex2mathml` 时，程序会通过 Office 自带的 `MML2OMML.XSL` 生成可编辑的 Word 原生公式；不可用时回退为可编辑 LaTeX 文本。

当前公式功能的边界：

- 识别尺寸适中的图片公式；
- 拒绝不含可靠数学特征的普通 OCR 文本；
- 跳过整页扫描图和过小图片；
- 暂不识别由 PDF 字体或矢量路径绘制的公式；
- 公式集中加入文末审阅区，暂不承诺可靠的原位置替换。

## 图片提取与分割

在桌面程序中勾选 **Extract and split PDF images**，或在命令行使用 `--split-images`。程序会在 DOCX 旁创建 `<文档名>_images` 文件夹，将提取和分割后的图片保存为 PNG。该功能只额外导出图片，不会改变 Word 中原有图片及其排版。

分割器会在 PDF 内嵌的位图中寻找明显的横向或纵向空白带，适合处理简单的多面板图、图片合集和网格拼图。如果找不到可靠分隔线，程序会保留完整图片，不会强行裁切。过小图片区域和疑似整页扫描图会被跳过。

`.conversion.json` 报告会记录来源页码、PDF 边界框、像素裁剪边界框、输出尺寸、分割方向、状态、警告和文件名。文件名采用 `page-0001_image-001_piece-01.png` 等格式，便于追溯每个分图的来源。

当前边界：

- 相互接触或重叠的子图可能无法分开；
- 共用复杂背景的子图可能无法分开；
- 不会把 PDF 矢量图形识别成独立对象；
- 图片输出目录已存在且非空时，默认拒绝覆盖，只有启用覆盖选项后才会继续。

## 命令行

```powershell
python -m pip install --no-build-isolation -e ".[portable]"
pdf2word document.pdf
pdf2word document.pdf --formula-ocr
pdf2word document.pdf --formula-ocr --max-formulae-per-page 12
pdf2word document.pdf --split-images
pdf2word document.pdf --split-images --max-images-per-page 50 --max-pieces-per-image 16
```

每次转换生成 DOCX 和 `.conversion.json` 报告。报告记录转换引擎、页数、图片数量、公式识别结果、图片分割结果、警告和耗时。

## 当前限制

- 暂不支持需要密码的 PDF；
- 暂不内置整页文字 OCR，纯扫描文档的正文可能不完整；
- 复杂表格、矢量公式和特殊字体无法保证完全还原；
- OCR 公式和分割图片用于论文或生产环境前必须人工核对；
- PDF 是固定版式，Word 是流式版式，两者无法在所有情况下完全一致。

欢迎通过 issue 提交脱敏后的失败样例描述和复现步骤。请勿上传无权公开的文件。
