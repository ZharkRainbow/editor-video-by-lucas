import sys, subprocess
src, dst, title = sys.argv[1], sys.argv[2], sys.argv[3]
raw = subprocess.run(["ffmpeg","-v","error","-i",src,"-f","rawvideo","-pix_fmt","rgb24","-"],
                     capture_output=True, check=True).stdout
N = 64                      # niveaux par canal (haldclutsrc=8 -> 8^2)
need = N**3 * 3
if len(raw) != need:
    sys.exit(f"taille inattendue: {len(raw)} au lieu de {need}")
out = [f'TITLE "{title}"', f"LUT_3D_SIZE {N}", "DOMAIN_MIN 0.0 0.0 0.0", "DOMAIN_MAX 1.0 1.0 1.0", ""]
for i in range(N**3):
    r, g, b = raw[3*i], raw[3*i+1], raw[3*i+2]
    out.append(f"{r/255:.6f} {g/255:.6f} {b/255:.6f}")
open(dst, "w").write("\n".join(out) + "\n")
print(f"{dst} ecrit : {N}^3 = {N**3} entrees")
