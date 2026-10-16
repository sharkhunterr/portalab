// Portalab — ambient/orion: the « orion » ambience (spec 028, B2)
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

// from the white-hot heart outwards: pink, crimson, magenta, violet, then the blue of the wings
vec3 orionColour(float x) {
  vec3 c = mix(vec3(1.0, 0.95, 0.97), vec3(1.0, 0.55, 0.75), smoothstep(0.0, 0.15, x));
  c = mix(c, vec3(0.97, 0.18, 0.4), smoothstep(0.12, 0.35, x));
  c = mix(c, vec3(0.75, 0.15, 0.6), smoothstep(0.35, 0.6, x));
  c = mix(c, vec3(0.38, 0.2, 0.7), smoothstep(0.55, 0.8, x));
  return mix(c, vec3(0.22, 0.35, 0.9), smoothstep(0.78, 1.0, x));
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = mod(u_time, 600.0);
  float aspect = u_res.x / u_res.y;
  vec2 q = (p - vec2(0.55 * aspect, 0.46)) * 1.25;
  vec2 w1 = vec2(fbm4(q * 1.1 + vec2(t * 0.014, 0.0)), fbm4(q * 1.1 + vec2(5.2, 1.3) - t * 0.011));
  vec2 w2 = vec2(fbm4(q * 1.9 + w1 * 2.2 + vec2(1.7, 9.2)), fbm4(q * 1.9 + w1 * 2.2 + vec2(8.3, 2.8) + t * 0.012));
  vec2 at = q * 1.5 + w2 * 2.4;
  float n = fbm(at);
  // the billows lit from the heart: brighter where the cloud rises towards it
  vec2 toHeart = normalize(vec2(-0.08, 0.2) - q + 1e-4);
  float lift = (fbm(at + toHeart * 0.06) - n) * 14.0;
  float r = length(q * vec2(0.82, 1.0));
  float envelope = smoothstep(1.25, 0.25, r + (w1.x - 0.5) * 0.7);
  float density = smoothstep(0.28, 0.66, n) * envelope;
  float core = length(q - vec2(-0.08, 0.2));
  vec3 col = orionColour(clamp(core * 0.85 + (0.62 - n) * 0.7 + (w2.y - 0.5) * 0.3, 0.0, 1.0));
  col *= 0.85 + 0.65 * clamp(0.5 + lift, 0.0, 1.0);
  float fil = ridged(q * 2.4 + w2 * 1.7 + vec2(0.0, t * 0.005));
  col += vec3(1.0, 0.7, 0.85) * pow(fil, 3.0) * 0.4 * density;
  float dust = smoothstep(0.6, 0.8, fbm4(q * 3.2 - w1 * 2.0 + 3.0)) * smoothstep(0.15, 0.8, core);
  float a = clamp(density * (0.65 + 0.45 * n) + exp(-core * 3.5) * 0.6, 0.0, 0.95) * (1.0 - dust * 0.85);
  vec4 o = vec4(col * a, a);
  vec2 m = q - vec2(-0.6, 0.66);
  float puff = smoothstep(0.26, 0.0, length(m) + (fbm4(m * 6.0 + t * 0.01) - 0.5) * 0.14);
  o = over(o, orionColour(clamp(length(m) * 3.0, 0.0, 0.6)), puff * 0.65);
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    vec2 s = q - vec2(-0.12 + 0.07 * mod(fi, 2.0), 0.18 + 0.06 * floor(fi / 2.0) + 0.012 * fi);
    float tw = 0.85 + 0.15 * sin(t * (2.0 + fi) + fi);
    o = over(o, vec3(0.88, 0.94, 1.0), clamp(spiked(s, 0.011) * tw, 0.0, 1.0));
  }
  o = over(o, vec3(1.0, 0.96, 0.92), starfield(p, 75.0, t, 0.03) * (1.0 - density * 0.6));
  o = over(o, vec3(0.75, 0.82, 1.0), starfield(p + 3.0, 150.0, t, 0.025) * 0.6 * (1.0 - density * 0.5));
  o = brightStars(o, p, aspect, t, 11.0, 4.0);
  gl_FragColor = o;
}