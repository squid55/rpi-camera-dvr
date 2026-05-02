"""DVR pipeline supervisor.

rpicam-vid (H.264 baseline, inline SPS/PPS, 2s GOP)
   -> ffmpeg
        -> /srv/dvr/dvr.m3u8 + seg_*.ts        (HLS DVR for time-shift)
        -> rtsp://localhost:8554/cam           (MediaMTX -> WebRTC live)

The 8080 MJPEG output was removed: the multiboard viewer's RPi 3B panel
will SYN-error and stay blank. Use http://<host>:8090/player/ instead -
the DVR page handles live (WebRTC, ~0.2s) and seek-back (HLS).
"""
import subprocess
import time

DVR_DIR = "/srv/dvr"
WIDTH, HEIGHT = 1280, 720
FPS = 15
RTSP_URL = "rtsp://localhost:8554/cam"


def run_pipeline():
    rpicam = None
    ffmpeg = None
    try:
        rpicam = subprocess.Popen(
            ["rpicam-vid", "-t", "0",
             "--width", str(WIDTH), "--height", str(HEIGHT),
             "--framerate", str(FPS),
             "--codec", "h264",
             "--profile", "baseline",
             "--inline",
             "--intra", str(FPS * 2),
             "--bitrate", "1000000",
             "-o", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )
        ffmpeg = subprocess.Popen(
            ["ffmpeg", "-loglevel", "warning", "-y",
             "-f", "h264", "-i", "-",
             "-map", "0:v", "-c:v", "copy",
             "-f", "hls", "-hls_time", "2", "-hls_list_size", "0",
             "-hls_playlist_type", "event",
             "-hls_flags",
             "independent_segments+program_date_time+append_list",
             "-strftime", "1",
             "-hls_segment_filename",
             DVR_DIR + "/seg_%Y%m%dT%H%M%S.ts",
             DVR_DIR + "/dvr.m3u8",
             "-map", "0:v", "-c:v", "copy",
             "-f", "rtsp", "-rtsp_transport", "tcp",
             RTSP_URL],
            stdin=rpicam.stdout,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        rpicam.stdout.close()
        ffmpeg.wait()
    finally:
        for p in (rpicam, ffmpeg):
            if p is None:
                continue
            try:
                p.terminate()
            except Exception:
                pass


def main():
    print("RPi3B DVR pipeline: HLS={}, RTSP={}".format(DVR_DIR, RTSP_URL))
    while True:
        try:
            run_pipeline()
        except Exception:
            pass
        time.sleep(3)


if __name__ == "__main__":
    main()
