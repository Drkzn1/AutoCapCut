# AutoCapCut

Tự động khớp ảnh/video với file voice thành một project CapCut hoàn chỉnh.

Đưa vào: file voice, file SRT (hoặc để tool tự nhận dạng), danh sách scene, thư
mục ảnh/video. Nhận về: một dự án CapCut mở lên là chỉnh sửa được ngay, đã có
sẵn timeline khớp lời, phụ đề và chuyển động Ken Burns cho từng cảnh.

## Chạy

Bấm đúp `AutoCapCut.command` trong Finder, hoặc:

```bash
cd ~/AutoCapCut
./AutoCapCut.command    # mở giao diện
```

Hoặc chạy bằng dòng lệnh khi cần làm hàng loạt:

```bash
.venv/bin/python main.py \
  --voice voice.mp3 \
  --srt voice.srt \
  --scenes scenes.txt \
  --media ./anh \
  --name "Video so 1"
```

Chưa có SRT thì bỏ `--srt` đi, tool tự nhận dạng lời trong file voice:

```bash
.venv/bin/python main.py --voice voice.mp3 --auto-srt --whisper-model small \
  --scenes scenes.txt --media ./anh --name "Video so 1"
```

`--help` để xem hết tuỳ chọn.

## Build cho Windows (làm trên máy Windows)

PyInstaller không build chéo hệ điều hành: máy Mac chỉ ra được file cho Mac.
Muốn có `.exe` thì phải chạy build trên chính máy Windows.

1. Clone repo này về máy Windows.
2. Cài Python 3.9-3.12 từ python.org, lúc cài **bắt buộc tick "Add python.exe
   to PATH"**.
3. Bấm đúp `build_windows.bat`, chờ 5-15 phút.

Kết quả: `dist-win\AutoCapCut Studio\AutoCapCut Studio.exe`

Gửi cho người khác thì nén **cả thư mục** `AutoCapCut Studio` rồi gửi - file
`.exe` cần các file xung quanh mới chạy. Người nhận không cần cài Python, chỉ
cần có CapCut và đã từng tạo ít nhất một dự án trong đó.

Chi tiết và cách xử lý lỗi: `docs/BUILD TREN WINDOWS.txt`

## Cách tool khớp scene với thời gian

Đây là phần lõi. SRT do máy nhận dạng gần như không bao giờ cắt câu giống hệt
kịch bản: nó gộp câu, tách câu, nghe sai từ. Nên tool **không** ghép cứng theo
chỉ số dòng.

Thay vào đó:

1. Đưa cả danh sách scene lẫn nội dung SRT về chuỗi từ đã bỏ dấu, bỏ dấu câu.
   Bỏ dấu là cố ý — nhận dạng tiếng Việt rất hay sai dấu, so phần chữ trần cho
   tỷ lệ khớp cao hơn hẳn.
2. Dùng `difflib.SequenceMatcher` tìm các đoạn trùng, suy ra từ đầu tiên của
   mỗi scene rơi vào block SRT nào. Mốc bắt đầu scene = mốc bắt đầu block đó.
3. Scene không khớp được chữ nào (ví dụ chỉ mô tả hình ảnh) được nội suy đều
   giữa hai scene khớp gần nhất.
4. Nhiều scene rơi trúng cùng một mốc thì chia đều khoảng thời gian tới mốc kế
   tiếp, thay vì để chúng chồng lên nhau rồi bị cắt còn một frame.
5. Khớp được dưới 35% số từ thì coi như scene và SRT không cùng nội dung, quay
   về chia đều theo tỷ lệ.

Kết quả: kể cả khi Whisper nghe nhầm "trôi giữa dòng sông" thành "chôi giữa
rồng xông", scene vẫn rơi đúng ranh giới câu.

## Chuyển động Ken Burns

CapCut tính vị trí theo **nửa chiều canvas**: giá trị `1.0` = dịch đúng nửa
chiều rộng khung hình. Đổi từ pixel sang giá trị draft là `px / (canvas / 2)`.

Hệ quả: ở mức phóng `s`, ảnh chỉ trượt được tối đa `s - 1.0` đơn vị mỗi phía
trước khi lộ mép đen. Với scale 110% trên khung 1920x1080, biên đó đúng bằng
±96px ngang và ±54px dọc — nên biên độ mặc định là X=190, Y=108 (tổng quãng
đường, chia đôi cho mỗi phía). Nhập quá biên thì tool tự cắt bớt.

## Tương thích CapCut

Bản Windows đọc `draft_content.json`, bản macOS đọc `draft_info.json` — tool ghi
đúng theo nền tảng đang chạy.

Ngoài ra CapCut giữ một danh mục `root_meta_info.json`; không thêm bản ghi vào
đó thì draft vẫn hợp lệ nhưng không hiện ở màn hình chính. Tool tự đăng ký, có
sao lưu file danh mục gốc trước khi sửa.

Thư viện `pycapcut` viết cứng `platform` là Windows/CapCut 6.7.0. Module
`compat.py` chép lại đúng khối `platform` từ một draft có sẵn của bạn (đã có
device_id, app_version, os đúng như CapCut tự ghi), nên draft sinh ra trông
giống hàng chính chủ.

**Lưu ý:** thoát hẳn CapCut trước khi tạo project. CapCut ghi đè danh mục khi
thoát, nên nếu nó đang mở thì dự án mới có thể không hiện ra.

## Cấu trúc

| File | Việc |
|---|---|
| `srt.py` | Đọc SRT, chịu được file thiếu số thứ tự, sai bảng mã, có rác |
| `scenes.py` | Khớp scene với mốc thời gian — phần lõi |
| `media.py` | Quét thư mục, sắp xếp tự nhiên (`anh2` trước `anh10`) |
| `motion.py` | Sinh keyframe zoom/pan |
| `transcribe.py` | Nhận dạng giọng nói bằng faster-whisper, tự cắt dòng phụ đề |
| `builder.py` | Ghép tất cả thành timeline |
| `capcut.py` | Ghi draft, đăng ký vào danh mục CapCut |
| `compat.py` | Vá thông tin nền tảng cho khớp bản CapCut đang cài |
| `gui.py` | Giao diện |
| `cli.py` | Dòng lệnh |

## Model nhận dạng

`tiny` / `base` chạy rất nhanh nhưng sai nhiều với tiếng Việt. Nên dùng `small`
trở lên nếu phụ đề được chèn vào video. Model tải về lần đầu rồi nằm lại trong
`~/.autocapcut/models`, các lần sau chạy offline.

SRT tự nhận dạng luôn được ghi ra file cạnh file voice, mở sửa lại rồi chạy lại
với `--srt` là xong, không phải nhận dạng lần nữa.
