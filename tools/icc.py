"""Read and write the ICC v2 profiles Capture One uses for camera input (RGB -> Lab, A2B0 mft2),
and read simple matrix/TRC RGB profiles."""
import struct

import numpy as np

D50 = np.array([0.9642, 1.0, 0.8249])


def s15(b):
    return struct.unpack(">i", b)[0] / 65536.0


def parse_tags(data):
    count = struct.unpack(">I", data[128:132])[0]
    tags = {}
    order = []
    for i in range(count):
        sig, off, size = struct.unpack(">4sII", data[132 + 12 * i : 144 + 12 * i])
        name = sig.decode("latin1")
        tags[name] = data[off : off + size]
        order.append(name)
    return tags, order


class Mft2:
    def __init__(self, matrix, in_curves, clut, out_curves):
        self.matrix = matrix  # 3x3 float
        self.in_curves = in_curves  # (3, n_in) uint16
        self.clut = clut  # (G, G, G, 3) uint16, index order [r][g][b]
        self.out_curves = out_curves  # (3, n_out) uint16

    @property
    def grid(self):
        return self.clut.shape[0]

    @classmethod
    def parse(cls, b):
        assert b[:4] == b"mft2", b[:4]
        ich, och, grid = b[8], b[9], b[10]
        assert ich == 3 and och == 3
        matrix = np.array(struct.unpack(">9i", b[12:48]), dtype=float).reshape(3, 3) / 65536.0
        n_in, n_out = struct.unpack(">HH", b[48:52])
        p = 52
        in_curves = np.frombuffer(b, dtype=">u2", count=3 * n_in, offset=p).reshape(3, n_in).astype(np.uint16)
        p += 6 * n_in
        clut = np.frombuffer(b, dtype=">u2", count=grid**3 * 3, offset=p).reshape(grid, grid, grid, 3).astype(np.uint16)
        p += 6 * grid**3
        out_curves = np.frombuffer(b, dtype=">u2", count=3 * n_out, offset=p).reshape(3, n_out).astype(np.uint16)
        return cls(matrix, in_curves, clut, out_curves)

    def serialize(self):
        g = self.grid
        out = bytearray(b"mft2\0\0\0\0")
        out += bytes([3, 3, g, 0])
        out += struct.pack(">9i", *[int(round(v * 65536)) for v in self.matrix.flatten()])
        out += struct.pack(">HH", self.in_curves.shape[1], self.out_curves.shape[1])
        out += self.in_curves.astype(">u2").tobytes()
        out += self.clut.astype(">u2").tobytes()
        out += self.out_curves.astype(">u2").tobytes()
        return bytes(out)


def lab_from_legacy16(v):
    v = np.asarray(v, dtype=float)
    return np.stack([v[..., 0] / 65280.0 * 100.0, v[..., 1] / 256.0 - 128.0, v[..., 2] / 256.0 - 128.0], axis=-1)


def lab_to_legacy16(lab):
    lab = np.asarray(lab, dtype=float)
    L = np.clip(lab[..., 0], 0, 100) / 100.0 * 65280.0
    a = (np.clip(lab[..., 1], -128, 127.996) + 128.0) * 256.0
    b = (np.clip(lab[..., 2], -128, 127.996) + 128.0) * 256.0
    return np.clip(np.round(np.stack([L, a, b], axis=-1)), 0, 65535).astype(np.uint16)


def desc_tag(text):
    ascii_bytes = text.encode("ascii") + b"\0"
    out = bytearray(b"desc\0\0\0\0")
    out += struct.pack(">I", len(ascii_bytes)) + ascii_bytes
    out += struct.pack(">II", 0, 0)  # unicode language code, count
    out += struct.pack(">HB", 0, 0) + b"\0" * 67  # scriptcode code, count, 67 bytes
    return bytes(out)


def text_tag(text):
    return b"text\0\0\0\0" + text.encode("ascii") + b"\0"


def xyz_tag(xyz):
    return b"XYZ \0\0\0\0" + struct.pack(">3i", *[int(round(v * 65536)) for v in xyz])


def build_profile(header_template, tag_list):
    """tag_list: list of (sig, bytes). Header fields other than size are copied from the template."""
    n = len(tag_list)
    table_size = 4 + 12 * n
    offset = 128 + table_size
    blobs = bytearray()
    table = bytearray(struct.pack(">I", n))
    for sig, blob in tag_list:
        while (offset + len(blobs)) % 4:
            blobs += b"\0"
        table += struct.pack(">4sII", sig.encode("latin1"), offset + len(blobs), len(blob))
        blobs += blob
    while (offset + len(blobs)) % 4:
        blobs += b"\0"
    header = bytearray(header_template[:128])
    total = 128 + len(table) + len(blobs)
    header[0:4] = struct.pack(">I", total)
    header[84:100] = b"\0" * 16  # profile ID (unused in v2)
    return bytes(header) + bytes(table) + bytes(blobs)


class InputProfile:
    def __init__(self, path):
        self.data = open(path, "rb").read()
        self.tags, self.order = parse_tags(self.data)
        self.a2b0 = Mft2.parse(self.tags["A2B0"])

    def desc(self):
        b = self.tags["desc"]
        n = struct.unpack(">I", b[8:12])[0]
        return b[12 : 12 + n].split(b"\0")[0].decode("latin1")

    def evaluate(self, rgb):
        """rgb in [0,1], shape (...,3) -> Lab. Trilinear, as a CMM would do with mft2."""
        return eval_mft2(self.a2b0, rgb)


def _interp_curve(curve_u16, x):
    n = curve_u16.shape[0]
    t = np.clip(x, 0, 1) * (n - 1)
    i = np.minimum(np.floor(t).astype(int), n - 2)
    f = t - i
    c = curve_u16.astype(float) / 65535.0
    return c[i] * (1 - f) + c[i + 1] * f


def eval_mft2(m, rgb):
    rgb = np.asarray(rgb, dtype=float)
    shaped = np.stack([_interp_curve(m.in_curves[c], rgb[..., c]) for c in range(3)], axis=-1)
    g = m.grid
    t = shaped * (g - 1)
    i0 = np.minimum(np.floor(t).astype(int), g - 2)
    f = t - i0
    clut = m.clut.astype(float)
    acc = np.zeros(rgb.shape[:-1] + (3,))
    for dr in (0, 1):
        wr = f[..., 0] if dr else 1 - f[..., 0]
        for dg in (0, 1):
            wg = f[..., 1] if dg else 1 - f[..., 1]
            for db in (0, 1):
                wb = f[..., 2] if db else 1 - f[..., 2]
                acc += (wr * wg * wb)[..., None] * clut[i0[..., 0] + dr, i0[..., 1] + dg, i0[..., 2] + db]
    acc /= 65535.0
    out = np.stack([_interp_curve(m.out_curves[c], acc[..., c]) for c in range(3)], axis=-1) * 65535.0
    return lab_from_legacy16(out)


class MatrixProfile:
    """RGB matrix/TRC profile (v2 or v4 with curv/para)."""

    def __init__(self, path):
        self.data = open(path, "rb").read()
        self.tags, _ = parse_tags(self.data)
        self.M = np.array([[s15(self.tags[t][8 + 4 * k : 12 + 4 * k]) for t in ("rXYZ", "gXYZ", "bXYZ")] for k in range(3)])
        self.trc = [self.tags[t] for t in ("rTRC", "gTRC", "bTRC")]
        self.wtpt = np.array([s15(self.tags["wtpt"][8 + 4 * k : 12 + 4 * k]) for k in range(3)])

    def describe_trc(self, i=0):
        b = self.trc[i]
        if b[:4] == b"curv":
            n = struct.unpack(">I", b[8:12])[0]
            if n == 0:
                return "identity"
            if n == 1:
                return "gamma %.6f" % (struct.unpack(">H", b[12:14])[0] / 256.0)
            return "table %d" % n
        if b[:4] == b"para":
            ftype = struct.unpack(">H", b[8:10])[0]
            params = [s15(b[12 + 4 * k : 16 + 4 * k]) for k in range((len(b) - 12) // 4)]
            return "para type %d %s" % (ftype, [round(p, 6) for p in params])
        return b[:4]

    def decode(self, v, i):
        b = self.trc[i]
        v = np.clip(np.asarray(v, dtype=float), 0, 1)
        if b[:4] == b"curv":
            n = struct.unpack(">I", b[8:12])[0]
            if n == 0:
                return v
            if n == 1:
                return v ** (struct.unpack(">H", b[12:14])[0] / 256.0)
            table = np.frombuffer(b, dtype=">u2", count=n, offset=12).astype(float) / 65535.0
            return np.interp(v, np.linspace(0, 1, n), table)
        if b[:4] == b"para":
            ftype = struct.unpack(">H", b[8:10])[0]
            p = [s15(b[12 + 4 * k : 16 + 4 * k]) for k in range((len(b) - 12) // 4)]
            g = p[0]
            if ftype == 0:
                return v**g
            if ftype == 3:
                _, a, bb, c, d = p[:5]
                return np.where(v >= d, (a * v + bb) ** g, c * v)
            raise NotImplementedError(ftype)
        raise NotImplementedError(b[:4])

    def to_xyz(self, rgb):
        rgb = np.asarray(rgb, dtype=float)
        lin = np.stack([self.decode(rgb[..., c], c) for c in range(3)], axis=-1)
        return lin @ self.M.T


def xyz_to_lab(xyz, white=D50):
    t = np.asarray(xyz, dtype=float) / white
    e = 216 / 24389
    k = 24389 / 27
    f = np.where(t > e, np.cbrt(t), (k * t + 16) / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def lab_to_xyz(lab, white=D50):
    lab = np.asarray(lab, dtype=float)
    fy = (lab[..., 0] + 16) / 116
    fx = fy + lab[..., 1] / 500
    fz = fy - lab[..., 2] / 200
    e = 216 / 24389
    k = 24389 / 27

    def finv(f):
        return np.where(f**3 > e, f**3, (116 * f - 16) / k)

    return np.stack([finv(fx), finv(fy), finv(fz)], axis=-1) * white


def de2000(lab1, lab2):
    L1, a1, b1 = np.moveaxis(np.asarray(lab1, dtype=float), -1, 0)
    L2, a2, b2 = np.moveaxis(np.asarray(lab2, dtype=float), -1, 0)
    C1 = np.hypot(a1, b1)
    C2 = np.hypot(a2, b2)
    Cm = (C1 + C2) / 2
    G = 0.5 * (1 - np.sqrt(Cm**7 / (Cm**7 + 25.0**7)))
    a1p = (1 + G) * a1
    a2p = (1 + G) * a2
    C1p = np.hypot(a1p, b1)
    C2p = np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp = L2 - L1
    dCp = C2p - C1p
    dh = h2p - h1p
    dh = np.where(C1p * C2p == 0, 0, np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh)))
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh / 2))
    Lpm = (L1 + L2) / 2
    Cpm = (C1p + C2p) / 2
    hsum = h1p + h2p
    hpm = np.where(
        C1p * C2p == 0,
        hsum,
        np.where(np.abs(h1p - h2p) <= 180, hsum / 2, np.where(hsum < 360, (hsum + 360) / 2, (hsum - 360) / 2)),
    )
    T = (
        1
        - 0.17 * np.cos(np.radians(hpm - 30))
        + 0.24 * np.cos(np.radians(2 * hpm))
        + 0.32 * np.cos(np.radians(3 * hpm + 6))
        - 0.20 * np.cos(np.radians(4 * hpm - 63))
    )
    dtheta = 30 * np.exp(-(((hpm - 275) / 25) ** 2))
    Rc = 2 * np.sqrt(Cpm**7 / (Cpm**7 + 25.0**7))
    Sl = 1 + 0.015 * (Lpm - 50) ** 2 / np.sqrt(20 + (Lpm - 50) ** 2)
    Sc = 1 + 0.045 * Cpm
    Sh = 1 + 0.015 * Cpm * T
    Rt = -np.sin(np.radians(2 * dtheta)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))
