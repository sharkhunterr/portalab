// Portalab — ambient/summerfield: the « summerfield » ambience (spec 028, B2)
float hillAt(float x, float base, float a, float f, float ph) {
  return base + a * sin(x * f + ph) + a * 0.5 * sin(x * f * 2.3 + ph * 1.7);
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  o = over(o, mix(vec3(0.55, 0.78, 1.0), vec3(0.25, 0.52, 0.95), uv.y), 0.3 + smoothstep(0.25, 1.0, uv.y) * 0.3);
  vec2 sun = vec2(aspect * 0.12, 0.86);
  float rs = length(p - sun);
  float ang = atan(p.y - sun.y, p.x - sun.x);
  o = over(o, vec3(1.0, 0.9, 0.5), exp(-rs * 4.0) * 0.35);
  o = over(o, vec3(1.0, 0.92, 0.55), smoothstep(0.004, 0.0, abs(rs - 0.075 - 0.012 * sin(ang * 12.0 + t))) * step(0.07, rs) * 0.5);
  o = over(o, vec3(1.0, 0.93, 0.6), smoothstep(0.052, 0.048, rs));
  // fluffy clouds: lit tops, a soft grey-blue underside
  for (int l = 0; l < 2; l++) {
    float fl = float(l);
    vec2 cq = vec2(p.x * (1.4 + fl * 0.8) - t * (0.015 + fl * 0.01) + fl * 5.0, uv.y * (3.0 + fl));
    float c = fbm(cq) + 0.5 * fbm(cq * 2.0 + 3.0) - 0.15;
    float band = smoothstep(0.5, 0.75, uv.y) * smoothstep(1.0, 0.85, uv.y);
    float cloud = smoothstep(0.62, 0.72, c * band + 0.25 * band);
    float under = smoothstep(0.0, 0.1, fbm(cq + vec2(0.0, 0.15)) - fbm(cq));
    o = over(o, mix(vec3(1.0), vec3(0.82, 0.88, 0.97), under * 0.8), cloud * (0.92 - fl * 0.2));
  }
  // the far hills with their little trees, the middle ones in patchwork fields, the near meadow
  float h1 = hillAt(p.x, 0.27, 0.025, 2.1, 1.0);
  float tree = step(0.6, hash(vec2(floor(p.x * 60.0), 1.0))) * smoothstep(0.006, 0.004, length(vec2((fract(p.x * 60.0) - 0.5) / 60.0, p.y - h1 - 0.006)));
  o = over(o, mix(vec3(0.5, 0.72, 0.55), vec3(0.4, 0.66, 0.4), smoothstep(h1, h1 - 0.06, p.y)) * (0.92 + 0.12 * fbm(p * 12.0)), max(step(p.y, h1), tree * 0.9) * 0.95);
  o = over(o, vec3(0.25, 0.45, 0.28), tree);
  float h2 = hillAt(p.x, 0.19, 0.03, 1.6, 2.5);
  vec2 fq = mat2(0.9, -0.44, 0.44, 0.9) * p * vec2(9.0, 22.0);
  float field = hash(floor(fq));
  vec3 fieldc = field < 0.3 ? vec3(0.85, 0.78, 0.35) : field < 0.6 ? vec3(0.45, 0.72, 0.32) : field < 0.8 ? vec3(0.62, 0.8, 0.38) : vec3(0.7, 0.55, 0.35);
  float hedge = smoothstep(0.06, 0.0, min(fract(fq.x), fract(fq.y)));
  fieldc *= 0.9 + 0.2 * noise(fq * 4.0 + p * 80.0);
  o = over(o, mix(fieldc, vec3(0.2, 0.4, 0.22), hedge * 0.8), step(p.y, h2));
  float h3 = hillAt(p.x, 0.1, 0.025, 1.1, 4.0);
  float meadow = step(p.y, h3);
  o = over(o, mix(vec3(0.3, 0.6, 0.25), vec3(0.42, 0.72, 0.3), fbm(p * 8.0)), meadow);
  // flowers on the meadow, nodding
  vec2 fg = p * vec2(70.0, 70.0);
  vec2 fid = floor(fg);
  float fh = hash(fid + 5.0);
  vec2 fp = fract(fg) - 0.5 - vec2(sin(t * 1.5 + fid.x * 0.7) * 0.12, 0.0);
  float bloom = smoothstep(0.24, 0.16, length(fp)) * step(0.82, fh) * step(p.y, h3 - 0.01);
  vec3 petal = fh < 0.87 ? vec3(1.0, 0.3, 0.3) : fh < 0.91 ? vec3(1.0, 0.85, 0.2) : fh < 0.95 ? vec3(1.0, 1.0, 1.0) : vec3(0.75, 0.45, 1.0);
  o = over(o, petal, bloom);
  o = over(o, vec3(1.0, 0.85, 0.3), smoothstep(0.08, 0.04, length(fp)) * bloom);
  // grass blades swaying in the breeze, two rows
  for (int l = 0; l < 2; l++) {
    float fl = float(l);
    float k = 150.0 + fl * 70.0;
    float bx = floor(p.x * k + fl * 0.5);
    float bh = (0.035 + 0.05 * hash(vec2(bx, fl + 2.0))) * (1.0 - fl * 0.3);
    float yy = clamp(p.y / bh, 0.0, 1.0);
    float lean = (sin(t * 1.3 + bx * 0.15 + fl) * 0.8 + 0.4 * sin(t * 2.7 + bx * 0.4)) * yy * yy * 1.5;
    float fx = fract(p.x * k + fl * 0.5) - 0.5 - lean;
    float blade = step(abs(fx), 0.35 * (1.0 - yy)) * step(p.y, bh);
    o = over(o, mix(vec3(0.2, 0.45, 0.15), vec3(0.45, 0.75, 0.3), yy) * (1.0 - fl * 0.15), blade);
  }
  gl_FragColor = o;
}