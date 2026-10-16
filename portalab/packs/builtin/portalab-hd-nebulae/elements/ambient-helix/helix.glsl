// Portalab — ambient/helix: the « helix » ambience (spec 028, B2)
float fbm4(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  mat2 turn = mat2(0.8, 0.6, -0.6, 0.8);
  for (int i = 0; i < 4; i++) {
    v += a * noise(p);
    p = turn * p * 2.03 + vec2(1.7, 9.2);
    a *= 0.5;
  }
  return v;
}
// thin bright filaments: the creases of a noise, sharpened octave after octave
float ridged(vec2 p) {
  float v = 0.0;
  float a = 0.55;
  float prev = 1.0;
  mat2 turn = mat2(0.8, 0.6, -0.6, 0.8);
  for (int i = 0; i < 5; i++) {
    float n = 1.0 - abs(2.0 * noise(p) - 1.0);
    n = n * n;
    v += n * a * prev;
    prev = n;
    p = turn * p * 2.1 + vec2(3.1, 7.7);
    a *= 0.5;
  }
  return v;
}
float starfield(vec2 p, float scale, float t, float density) {
  vec2 sg = p * scale;
  vec2 id = floor(sg);
  float h = hash(id);
  vec2 at = vec2(hash(id + 3.1), hash(id + 7.7)) - 0.5;
  float s = step(1.0 - density, h) * smoothstep(0.12 + 0.1 * hash(id + 1.3), 0.0, length(fract(sg) - 0.5 - at * 0.6));
  return s * (0.55 + 0.45 * sin(t * (1.0 + 2.0 * hash(id + 5.0)) + h * 40.0));
}
// a star seen by a great telescope: a bright core, a halo and six diffraction spikes (two short ones across)
float spiked(vec2 d, float size) {
  float r = length(d);
  float core = exp(-r / size * 3.2) + exp(-r / size * 0.9) * 0.18;
  float spikes = 0.0;
  for (int i = 0; i < 3; i++) {
    float a = float(i) * 1.0472 + 1.5708;
    vec2 dir = vec2(cos(a), sin(a));
    float along = abs(dot(d, dir));
    float across = abs(dot(d, vec2(-dir.y, dir.x)));
    spikes += exp(-across / size * 9.0) * exp(-along / size * 0.55);
  }
  spikes += 0.5 * exp(-abs(d.y) / size * 9.0) * exp(-abs(d.x) / size * 1.1);
  return core + spikes * 0.55;
}
// a few big stars with their spikes, slowly twinkling, coloured blue-white to gold
vec4 brightStars(vec4 o, vec2 p, float aspect, float t, float seed, float count) {
  for (int i = 0; i < 7; i++) {
    float fi = float(i);
    if (fi >= count) break;
    vec2 at = vec2(hash(vec2(fi, seed)) * aspect, 0.08 + hash(vec2(fi, seed + 1.0)) * 0.86);
    float size = 0.006 + 0.008 * hash(vec2(fi, seed + 2.0));
    float tw = 0.75 + 0.25 * sin(t * (0.7 + hash(vec2(fi, seed + 3.0))) + fi * 2.0);
    vec3 col = mix(vec3(0.75, 0.85, 1.0), vec3(1.0, 0.88, 0.7), hash(vec2(fi, seed + 4.0)));
    o = over(o, col, clamp(spiked(p - at, size) * tw, 0.0, 1.0));
  }
  return o;
}

void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = mod(u_time, 600.0);
  float aspect = u_res.x / u_res.y;
  vec2 q = (p - vec2(0.55 * aspect, 0.5)) * 1.7;
  float turn = t * 0.01;
  q = mat2(cos(turn), -sin(turn), sin(turn), cos(turn)) * q;
  q.x *= 0.88;
  float r = length(q) * (1.0 + 0.015 * sin(t * 0.3));
  float ang = atan(q.y, q.x);
  vec2 polar = vec2(ang * 3.0, r * 2.0);
  float wob = (fbm4(vec2(cos(ang), sin(ang)) * 2.0 + t * 0.01) - 0.5) * 0.18;
  vec4 o = vec4(0.0);
  float heart = exp(-r * r * 9.0);
  o = over(o, mix(vec3(0.1, 0.25, 0.75), vec3(0.4, 0.6, 1.0), heart), heart * 0.55);
  float inner = exp(-pow((r - 0.42 - wob) / 0.13, 2.0));
  float ripple = fbm(vec2(cos(ang), sin(ang)) * 3.0 + vec2(r * 4.0, t * 0.01));
  o = over(o, mix(vec3(0.9, 0.15, 0.1), vec3(1.0, 0.55, 0.15), ripple), inner * (0.45 + 0.45 * ripple));
  float outer = exp(-pow((r - 0.72 - wob * 1.3) / 0.24, 2.0));
  float rays = fbm4(vec2(ang * 9.0 / 6.2832 * 6.0, r * 1.5 - t * 0.01)) * 0.6 + 0.4 * fbm(vec2(cos(ang), sin(ang)) * 5.0 + r * 2.0);
  vec3 teal = mix(vec3(0.05, 0.45, 0.5), vec3(0.4, 0.95, 0.85), rays);
  o = over(o, teal, outer * (0.3 + 0.55 * rays));
  // cometary knots on the ring's inner edge, their tails pointing out
  vec2 kg = vec2(ang / 6.2832 * 70.0, (r - 0.55) * 22.0);
  vec2 kid = floor(kg);
  vec2 kf = fract(kg) - vec2(0.5, 0.2);
  float knot = step(0.55, hash(kid)) * step(abs(r - 0.6 - wob), 0.15) * smoothstep(0.18, 0.0, abs(kf.x)) * smoothstep(0.7, -0.1, kf.y) * step(-0.2, kf.y);
  o = over(o, vec3(0.75, 1.0, 0.95), knot * 0.5);
  float halo = exp(-pow((r - 1.05) / 0.25, 2.0)) * fbm4(polar + t * 0.005);
  o = over(o, vec3(0.6, 0.25, 0.2), halo * 0.3);
  o = over(o, vec3(1.0), clamp(spiked(q / 1.7, 0.005), 0.0, 1.0));
  o = over(o, vec3(0.85, 0.92, 1.0), starfield(p, 80.0, t, 0.035));
  o = over(o, vec3(1.0, 0.9, 0.85), starfield(p + 2.0, 160.0, t, 0.025) * 0.5);
  o = brightStars(o, p, aspect, t, 31.0, 3.0);
  gl_FragColor = o;
}