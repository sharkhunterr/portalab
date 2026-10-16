// Portalab — ambient/moonrise: the « moonrise » ambience (spec 028, B2)
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
  float horizon = 0.3;
  float rise = 0.62 + 0.04 * sin(t * 0.01);
  vec2 mc = vec2(0.62 * aspect, rise);
  float R = 0.16;
  vec2 m = (p - mc) / R;
  float r = length(m);
  vec4 o = vec4(0.0);
  o = over(o, vec3(0.08, 0.12, 0.25), 0.35 * smoothstep(horizon, 1.0, uv.y));
  o = over(o, vec3(1.0, 0.97, 0.9), starfield(p, 80.0, t, 0.03) * smoothstep(horizon + 0.1, 0.6, uv.y) * smoothstep(0.6, 2.5, r));
  o = over(o, vec3(0.75, 0.82, 1.0), exp(-max(r - 1.0, 0.0) * 1.2) * 0.35 * step(1.0, r) * step(horizon, uv.y));
  // the moon: seas, highlands, craters with their rays
  float seas = smoothstep(0.45, 0.65, fbm(m * 1.6 + 3.0));
  vec3 moon = mix(vec3(0.92, 0.91, 0.86), vec3(0.55, 0.56, 0.6), seas);
  for (int i = 0; i < 6; i++) {
    float fi = float(i);
    vec2 cc = vec2(hash(vec2(fi, 1.0)) - 0.5, hash(vec2(fi, 2.0)) - 0.5) * 1.4;
    float cr = 0.06 + 0.1 * hash(vec2(fi, 3.0));
    float d = length(m - cc);
    moon *= 1.0 - 0.12 * smoothstep(cr, cr * 0.6, d) + 0.07 * smoothstep(0.03, 0.0, abs(d - cr)) * step(0.0, (m - cc).x + (m - cc).y);
  }
  moon *= 0.85 + 0.15 * fbm4(m * 8.0);
  moon *= 0.75 + 0.25 * sqrt(max(0.0, 1.0 - r * r));
  float above = step(horizon, uv.y);
  o = over(o, moon, smoothstep(1.02, 0.98, r) * above);
  // thin clouds drifting across it
  float cloud = smoothstep(0.5, 0.75, fbm4(vec2(p.x * 2.0 - t * 0.02, p.y * 9.0))) * smoothstep(horizon, horizon + 0.2, uv.y) * smoothstep(0.9, 0.5, uv.y);
  o = over(o, vec3(0.35, 0.38, 0.5), cloud * 0.45);
  // the sea and the moon's path on it
  float sea = step(uv.y, horizon);
  o = over(o, vec3(0.02, 0.04, 0.09), sea * 0.85);
  float waves = noise(vec2(p.x * 40.0, (horizon - uv.y) * 160.0 / (horizon - uv.y + 0.05) - t * 2.0));
  float path = smoothstep(0.22 + (horizon - uv.y) * 0.6, 0.0, abs(p.x - mc.x)) * sea;
  o = over(o, vec3(0.9, 0.93, 1.0), path * smoothstep(0.55, 0.85, waves) * 0.9);
  o = over(o, vec3(0.7, 0.75, 0.9), smoothstep(0.004, 0.0, abs(uv.y - horizon)) * 0.4);
  gl_FragColor = o;
}