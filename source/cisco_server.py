#!/usr/bin/env python3
"""
Cisco TFTP & FTP Server - Windows GUI
Requires: pip install pyftpdlib tftpy
Run as Administrator for port 69 (TFTP) firewall access.
"""

import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
import socket
import os
import sys
import subprocess
import ipaddress
from datetime import datetime
from pathlib import Path

try:
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer
    from pyftpdlib.authorizers import DummyAuthorizer
except ImportError:
    messagebox.showerror("Missing Dependency", "Run: pip install pyftpdlib")
    sys.exit(1)

try:
    import tftpy
except ImportError:
    messagebox.showerror("Missing Dependency", "Run: pip install tftpy")
    sys.exit(1)

# ── Colors ────────────────────────────────────────────────────────────────────
DARK_BG      = "#0d1117"
PANEL_BG     = "#161b22"
BORDER       = "#21262d"
ACCENT_BLUE  = "#1f6feb"
ACCENT_GREEN = "#238636"
ACCENT_RED   = "#da3633"
ACCENT_GOLD  = "#d29922"
TEXT_PRIMARY = "#e6edf3"
TEXT_MUTED   = "#8b949e"
TEXT_CODE    = "#79c0ff"


def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "0.0.0.0"


def ts():
    return datetime.now().strftime("%H:%M:%S")


# ── TFTP Server ───────────────────────────────────────────────────────────────
class TFTPServer:
    def __init__(self, root_dir, host, port, log_cb):
        self.root_dir = root_dir
        self.host = host
        self.port = port
        self.log = log_cb
        self._server = None
        self._thread = None
        self.running = False

    def start(self):
        self._server = tftpy.TftpServer(self.root_dir)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self.running = True
        self.log(f"TFTP  ▶  {self.host}:{self.port}  root: {self.root_dir}", "ok")

    def _run(self):
        try:
            self._server.listen(self.host, self.port)
        except Exception as e:
            self.log(f"TFTP error: {e}", "error")
            self.running = False

    def stop(self):
        if self._server:
            try:
                self._server.stop()
            except Exception:
                pass
        self.running = False
        self.log("TFTP  ■  stopped", "warn")


# ── FTP Server ────────────────────────────────────────────────────────────────
class FTPServerWrapper:
    def __init__(self, root_dir, host, port, user, password, log_cb):
        self.root_dir = root_dir
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.log = log_cb
        self._server = None
        self._thread = None
        self.running = False

    def start(self):
        try:
            auth = DummyAuthorizer()
            auth.add_user(self.user, self.password, self.root_dir, perm="elradfmwMT")
            auth.add_anonymous(self.root_dir, perm="elr")

            handler = FTPHandler
            handler.authorizer = auth
            handler.passive_ports = range(60000, 60101)
            handler.banner = "Cisco FTP Server Ready"

            log_cb = self.log
            orig_connect    = handler.on_connect
            orig_disconnect = handler.on_disconnect

            def on_connect(self_h):
                log_cb(f"FTP  client connected: {self_h.remote_ip}", "ok")
                orig_connect(self_h)

            def on_disconnect(self_h):
                log_cb(f"FTP  client disconnected: {self_h.remote_ip}", "warn")
                orig_disconnect(self_h)

            handler.on_connect    = on_connect
            handler.on_disconnect = on_disconnect

            self._server = FTPServer((self.host, self.port), handler)
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            self.running = True
            self.log(f"FTP   ▶  {self.host}:{self.port}  user: {self.user}", "ok")
        except Exception as e:
            self.log(f"FTP start error: {e}", "error")

    def _run(self):
        try:
            self._server.serve_forever()
        except Exception as e:
            if self.running:
                self.log(f"FTP error: {e}", "error")
            self.running = False

    def stop(self):
        if self._server:
            try:
                self._server.close_all()
            except Exception:
                pass
        self.running = False
        self.log("FTP   ■  stopped", "warn")


# ── Main App ──────────────────────────────────────────────────────────────────
class CiscoServerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Cisco TFTP & FTP Server")
        self.geometry("900x700")
        self.minsize(820, 600)
        self.configure(bg=DARK_BG)
        self.resizable(True, True)
        self._tftp_srv = None
        self._ftp_srv  = None
        self._fw_rules = []
        self._build_ui()
        self._load_defaults()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._apply_style()

        # Header
        hdr = tk.Frame(self, bg=PANEL_BG, height=60)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="⚙  CISCO SERVER TOOLKIT",
                 font=("Courier New", 16, "bold"),
                 fg=TEXT_CODE, bg=PANEL_BG).pack(side="left", padx=20, pady=10)
        tk.Label(hdr, text="TFTP  •  FTP",
                 font=("Courier New", 10),
                 fg=TEXT_MUTED, bg=PANEL_BG).pack(side="left", padx=5)
        self._status_dot = tk.Label(hdr, text="●", font=("Arial", 14),
                                    fg=ACCENT_RED, bg=PANEL_BG)
        self._status_dot.pack(side="right", padx=20)
        self._status_lbl = tk.Label(hdr, text="STOPPED",
                                    font=("Courier New", 10, "bold"),
                                    fg=ACCENT_RED, bg=PANEL_BG)
        self._status_lbl.pack(side="right")

        # Body
        body = tk.Frame(self, bg=DARK_BG)
        body.pack(fill="both", expand=True, padx=12, pady=8)
        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(1, weight=1)

        left = tk.Frame(body, bg=DARK_BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._build_common(left)
        self._build_tftp(left)
        self._build_ftp(left)
        self._build_buttons(left)

        right = tk.Frame(body, bg=DARK_BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self._build_quickref(right)

        # Log
        log_frame = tk.LabelFrame(body, text=" 📋 Activity Log ",
                                  font=("Courier New", 9, "bold"),
                                  fg=TEXT_MUTED, bg=DARK_BG,
                                  bd=1, relief="flat",
                                  highlightbackground=BORDER,
                                  highlightthickness=1)
        log_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        self.log_widget = scrolledtext.ScrolledText(
            log_frame, height=10,
            bg="#010409", fg=TEXT_PRIMARY,
            font=("Courier New", 9),
            insertbackground=TEXT_PRIMARY,
            bd=0, relief="flat", state="disabled", wrap="word")
        self.log_widget.pack(fill="both", expand=True, padx=4, pady=4)
        self.log_widget.tag_config("ok",    foreground=ACCENT_GREEN)
        self.log_widget.tag_config("error", foreground=ACCENT_RED)
        self.log_widget.tag_config("warn",  foreground=ACCENT_GOLD)
        self.log_widget.tag_config("info",  foreground=TEXT_PRIMARY)

    def _apply_style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TCheckbutton", background=DARK_BG,
                    foreground=TEXT_PRIMARY, font=("Courier New", 9))
        s.map("TCheckbutton", background=[("active", DARK_BG)])

    def _panel(self, parent, title):
        f = tk.LabelFrame(parent, text=f" {title} ",
                          font=("Courier New", 9, "bold"),
                          fg=TEXT_MUTED, bg=DARK_BG, bd=1, relief="flat",
                          highlightbackground=BORDER, highlightthickness=1)
        f.pack(fill="x", pady=(0, 6))
        return f

    def _mk_entry(self, parent, var, show=None):
        e = tk.Entry(parent, textvariable=var,
                     bg=PANEL_BG, fg=TEXT_CODE,
                     insertbackground=TEXT_CODE,
                     font=("Courier New", 10),
                     relief="flat", bd=4,
                     highlightthickness=1,
                     highlightbackground=BORDER,
                     highlightcolor=ACCENT_BLUE)
        if show:
            e.config(show=show)
        return e

    def _build_common(self, parent):
        p = self._panel(parent, "🌐 Network & Directory")
        self._var_ip  = tk.StringVar()
        self._var_dir = tk.StringVar()

        row1 = tk.Frame(p, bg=DARK_BG)
        row1.pack(fill="x", padx=8, pady=3)
        tk.Label(row1, text="Bind IP", width=16, anchor="w",
                 font=("Courier New", 9), fg=TEXT_MUTED, bg=DARK_BG).pack(side="left")
        self._mk_entry(row1, self._var_ip).pack(side="left", fill="x", expand=True)
        tk.Button(row1, text="Auto", font=("Courier New", 8),
                  bg=BORDER, fg=TEXT_MUTED, relief="flat", bd=0, cursor="hand2",
                  command=lambda: self._var_ip.set(get_local_ip())).pack(side="left", padx=(4, 0))

        row2 = tk.Frame(p, bg=DARK_BG)
        row2.pack(fill="x", padx=8, pady=3)
        tk.Label(row2, text="Root Directory", width=16, anchor="w",
                 font=("Courier New", 9), fg=TEXT_MUTED, bg=DARK_BG).pack(side="left")
        self._mk_entry(row2, self._var_dir).pack(side="left", fill="x", expand=True)
        tk.Button(row2, text="Browse", font=("Courier New", 8),
                  bg=BORDER, fg=TEXT_MUTED, relief="flat", bd=0, cursor="hand2",
                  command=self._browse_dir).pack(side="left", padx=(4, 0))
        tk.Frame(p, bg=DARK_BG, height=4).pack()

    def _build_tftp(self, parent):
        p = self._panel(parent, "📂 TFTP Server  (UDP)")
        self._var_tftp_en   = tk.BooleanVar(value=True)
        self._var_tftp_port = tk.StringVar(value="69")

        hdr = tk.Frame(p, bg=DARK_BG)
        hdr.pack(fill="x", padx=8, pady=(4, 2))
        ttk.Checkbutton(hdr, text="Enable TFTP", variable=self._var_tftp_en).pack(side="left")

        row = tk.Frame(p, bg=DARK_BG)
        row.pack(fill="x", padx=8, pady=3)
        tk.Label(row, text="Port", width=16, anchor="w",
                 font=("Courier New", 9), fg=TEXT_MUTED, bg=DARK_BG).pack(side="left")
        port_entry = self._mk_entry(row, self._var_tftp_port)
        port_entry.config(width=10)
        port_entry.pack(side="left")
        tk.Frame(p, bg=DARK_BG, height=4).pack()

    def _build_ftp(self, parent):
        p = self._panel(parent, "🔒 FTP Server  (TCP)")
        self._var_ftp_en   = tk.BooleanVar(value=True)
        self._var_ftp_port = tk.StringVar(value="21")
        self._var_ftp_user = tk.StringVar(value="cisco")
        self._var_ftp_pass = tk.StringVar(value="cisco")

        hdr = tk.Frame(p, bg=DARK_BG)
        hdr.pack(fill="x", padx=8, pady=(4, 2))
        ttk.Checkbutton(hdr, text="Enable FTP", variable=self._var_ftp_en).pack(side="left")

        for lbl, var, show in [
            ("Port",     self._var_ftp_port, None),
            ("Username", self._var_ftp_user, None),
            ("Password", self._var_ftp_pass, "●"),
        ]:
            row = tk.Frame(p, bg=DARK_BG)
            row.pack(fill="x", padx=8, pady=3)
            tk.Label(row, text=lbl, width=16, anchor="w",
                     font=("Courier New", 9), fg=TEXT_MUTED, bg=DARK_BG).pack(side="left")
            self._mk_entry(row, var, show=show).pack(side="left", fill="x", expand=True)
        tk.Frame(p, bg=DARK_BG, height=4).pack()

    def _build_buttons(self, parent):
        f = tk.Frame(parent, bg=DARK_BG)
        f.pack(fill="x", pady=4)
        btn = dict(font=("Courier New", 11, "bold"), relief="flat", bd=0, cursor="hand2", pady=8)
        self._btn_start = tk.Button(f, text="▶  START SERVERS",
                                    bg=ACCENT_GREEN, fg="white",
                                    command=self._start_servers, **btn)
        self._btn_start.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self._btn_stop = tk.Button(f, text="■  STOP",
                                   bg=ACCENT_RED, fg="white",
                                   command=self._stop_servers, state="disabled", **btn)
        self._btn_stop.pack(side="left", fill="x", expand=True)
        tk.Button(f, text="🗑 Clear Log", font=("Courier New", 9),
                  bg=BORDER, fg=TEXT_MUTED, relief="flat", bd=0, cursor="hand2",
                  command=self._clear_log).pack(side="left", padx=(4, 0))

    def _build_quickref(self, parent):
        p = tk.LabelFrame(parent, text=" 💡 Cisco Quick Reference ",
                          font=("Courier New", 9, "bold"),
                          fg=TEXT_MUTED, bg=DARK_BG, bd=1, relief="flat",
                          highlightbackground=BORDER, highlightthickness=1)
        p.pack(fill="both", expand=True)

        cmds = [
            ("BACKUP RUNNING-CONFIG (TFTP)", [
                "Router# copy running-config tftp:",
                "  Address: <server-ip>",
                "  Filename: router-backup.cfg",
            ]),
            ("RESTORE CONFIG (TFTP)", [
                "Router# copy tftp: running-config",
                "  Address: <server-ip>",
                "  Filename: router-backup.cfg",
            ]),
            ("UPGRADE IOS (TFTP)", [
                "Router# copy tftp: flash:",
                "  Address: <server-ip>",
                "  Filename: c2900-universalk9-mz.bin",
                "Router# boot system flash c2900-universalk9-mz.bin",
            ]),
            ("BACKUP CONFIG (FTP)", [
                "Router# ip ftp username cisco",
                "Router# ip ftp password cisco",
                "Router# copy running-config ftp:",
                "  Address: <server-ip>",
                "  Filename: router-config.cfg",
            ]),
            ("RESTORE IOS VIA FTP", [
                "Router# copy ftp: flash:",
                "  Address: <server-ip>",
                "  Filename: new-ios.bin",
            ]),
            ("ROMMON TFTP RECOVERY", [
                "rommon 1> IP_ADDRESS=192.168.1.1",
                "rommon 2> IP_SUBNET_MASK=255.255.255.0",
                "rommon 3> DEFAULT_GATEWAY=192.168.1.254",
                "rommon 4> TFTP_SERVER=<server-ip>",
                "rommon 5> TFTP_FILE=c2900-universalk9-mz.bin",
                "rommon 6> tftpdnld",
            ]),
        ]

        canvas = tk.Canvas(p, bg=DARK_BG, highlightthickness=0)
        sb = tk.Scrollbar(p, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inner = tk.Frame(canvas, bg=DARK_BG)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        for title, lines in cmds:
            tk.Label(inner, text=title, font=("Courier New", 8, "bold"),
                     fg=ACCENT_GOLD, bg=DARK_BG, anchor="w").pack(fill="x", padx=8, pady=(10, 2))
            block = tk.Frame(inner, bg="#010409",
                             highlightbackground=BORDER, highlightthickness=1)
            block.pack(fill="x", padx=8, pady=(0, 2))
            for line in lines:
                tk.Label(block, text=line, font=("Courier New", 8),
                         fg=TEXT_CODE, bg="#010409",
                         anchor="w", justify="left").pack(fill="x", padx=6, pady=1)

    # ── Firewall ──────────────────────────────────────────────────────────────
    def _fw_add(self, name, protocol, port):
        cmd = (f'netsh advfirewall firewall add rule name="{name}" '
               f'protocol={protocol} dir=in localport={port} action=allow')
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if r.returncode == 0:
            self._log(f"Firewall  ✔  rule added: {name} ({protocol}/{port})", "ok")
        else:
            self._log(f"Firewall  ⚠  {name}: {(r.stdout + r.stderr).strip()}", "warn")
            self._log("Firewall  ⚠  Run as Administrator for automatic firewall rules", "warn")

    def _fw_remove(self, name):
        cmd = f'netsh advfirewall firewall delete rule name="{name}"'
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if r.returncode == 0:
            self._log(f"Firewall  ✔  rule removed: {name}", "ok")

    def _open_ports(self, tftp_en, tftp_port, ftp_en, ftp_port):
        self._fw_rules = []
        if tftp_en:
            n = f"CiscoServer_TFTP_{tftp_port}"
            self._fw_add(n, "UDP", tftp_port)
            self._fw_rules.append(n)
        if ftp_en:
            n = f"CiscoServer_FTP_{ftp_port}"
            self._fw_add(n, "TCP", ftp_port)
            self._fw_rules.append(n)
            pn = "CiscoServer_FTP_Passive"
            subprocess.run(
                f'netsh advfirewall firewall add rule name="{pn}" '
                'protocol=TCP dir=in localport=60000-60100 action=allow',
                shell=True, capture_output=True)
            self._fw_rules.append(pn)

    def _close_ports(self):
        for name in self._fw_rules:
            self._fw_remove(name)
        self._fw_rules = []

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _load_defaults(self):
        self._var_ip.set(get_local_ip())
        home = str(Path.home() / "cisco_files")
        os.makedirs(home, exist_ok=True)
        self._var_dir.set(home)
        self._log(f"Default root: {home}", "info")
        self._log("Configure and press  ▶ START SERVERS  (run as Admin for auto-firewall)", "info")

    def _browse_dir(self):
        d = filedialog.askdirectory(initialdir=self._var_dir.get())
        if d:
            self._var_dir.set(d)

    def _log(self, msg, tag="info"):
        self.log_widget.after(0, self._append_log, msg, tag)

    def _append_log(self, msg, tag):
        self.log_widget.config(state="normal")
        self.log_widget.insert(tk.END, f"[{ts()}] {msg}\n", tag)
        self.log_widget.see(tk.END)
        self.log_widget.config(state="disabled")

    def _clear_log(self):
        self.log_widget.config(state="normal")
        self.log_widget.delete("1.0", tk.END)
        self.log_widget.config(state="disabled")

    def _set_running(self, running):
        if running:
            self._status_dot.config(fg=ACCENT_GREEN)
            self._status_lbl.config(text="RUNNING", fg=ACCENT_GREEN)
            self._btn_start.config(state="disabled")
            self._btn_stop.config(state="normal")
        else:
            self._status_dot.config(fg=ACCENT_RED)
            self._status_lbl.config(text="STOPPED", fg=ACCENT_RED)
            self._btn_start.config(state="normal")
            self._btn_stop.config(state="disabled")

    # ── Server control ────────────────────────────────────────────────────────
    def _validate(self):
        ip = self._var_ip.get().strip()
        d  = self._var_dir.get().strip()
        err = []
        try:
            ipaddress.ip_address(ip)
        except ValueError:
            err.append(f"Invalid IP: {ip}")
        if not os.path.isdir(d):
            try:
                os.makedirs(d, exist_ok=True)
            except Exception as e:
                err.append(f"Cannot create directory: {e}")
        if not self._var_tftp_en.get() and not self._var_ftp_en.get():
            err.append("Enable at least one service.")
        if err:
            messagebox.showerror("Validation Error", "\n".join(err))
            return False
        return True

    def _start_servers(self):
        if not self._validate():
            return

        ip   = self._var_ip.get().strip()
        root = self._var_dir.get().strip()

        tftp_en = self._var_tftp_en.get()
        ftp_en  = self._var_ftp_en.get()
        try:
            tftp_port = int(self._var_tftp_port.get())
        except ValueError:
            tftp_port = 69
        try:
            ftp_port = int(self._var_ftp_port.get())
        except ValueError:
            ftp_port = 21

        # Auto-open firewall ports
        self._open_ports(tftp_en, tftp_port, ftp_en, ftp_port)

        started = False

        if tftp_en:
            try:
                self._tftp_srv = TFTPServer(root, ip, tftp_port, self._log)
                self._tftp_srv.start()
                started = True
            except Exception as e:
                self._log(f"Cannot start TFTP: {e}", "error")

        if ftp_en:
            try:
                self._ftp_srv = FTPServerWrapper(
                    root, ip, ftp_port,
                    self._var_ftp_user.get(),
                    self._var_ftp_pass.get(),
                    self._log)
                self._ftp_srv.start()
                started = True
            except Exception as e:
                self._log(f"Cannot start FTP: {e}", "error")

        if started:
            self._set_running(True)
            self._log(f"Root directory: {root}", "info")

    def _stop_servers(self):
        if self._tftp_srv:
            self._tftp_srv.stop()
            self._tftp_srv = None
        if self._ftp_srv:
            self._ftp_srv.stop()
            self._ftp_srv = None
        self._close_ports()
        self._set_running(False)

    def _on_close(self):
        self._stop_servers()
        self.destroy()


if __name__ == "__main__":
    app = CiscoServerApp()
    app.mainloop()
