// Portalab — ambient/solarsystem: the « solarsystem » ambience (spec 028, B2)
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
  vec4 o = vec4(0.0);
  o = over(o, vec3(1.0, 0.97, 0.9), starfield(p, 90.0, t, 0.025));
  vec2 sun = vec2(0.32 * aspect, 0.46);
  vec2 q = (p - sun) * vec2(1.0, 2.6);
  float rs = length(p - sun);
  o = over(o, vec3(1.0, 0.6, 0.2), exp(-rs * 6.0) * 0.5);
  o = over(o, vec3(1.0, 0.85, 0.5), exp(-rs * 18.0) * (0.9 + 0.1 * sin(t * 2.0)));
  o = over(o, vec3(1.0, 0.97, 0.85), smoothstep(0.045, 0.035, rs));
  // the belt, between the fourth and the fifth orbit
  float rq = length(q);
  float belt = smoothstep(0.03, 0.0, abs(rq - 0.6)) * step(0.985, hash(floor(vec2(atan(q.y, q.x) * 120.0 + t * 0.6, rq * 140.0))));
  o = over(o, vec3(0.75, 0.7, 0.65), belt * 0.7);
  for (int i = 0; i < 6; i++) {
    float fi = float(i);
    float rad = 0.16 + 0.11 * fi + (fi > 3.5 ? 0.08 : 0.0);
    o = over(o, vec3(0.5, 0.6, 0.9), smoothstep(0.004, 0.0, abs(rq - rad)) * 0.18);
    float a = t * 0.6 / pow(rad * 4.0, 1.5) + fi * 2.1;
    vec2 at = sun + vec2(cos(a), sin(a) / 2.6) * rad;
    float size = 0.012 + 0.006 * mod(fi * 5.0, 3.0) + (fi > 3.5 ? 0.012 : 0.0);
    vec2 d = p - at;
    float dp = length(d);
    vec3 hue = fi < 0.5 ? vec3(0.7, 0.65, 0.6) : fi < 1.5 ? vec3(0.95, 0.8, 0.5) : fi < 2.5 ? vec3(0.3, 0.55, 1.0)
      : fi < 3.5 ? vec3(0.9, 0.4, 0.25) : fi < 4.5 ? vec3(0.9, 0.75, 0.55) : vec3(0.85, 0.8, 0.6);
    float lit = 0.3 + 0.7 * smoothstep(-0.5, 0.9, dot(normalize(sun - at), d / max(dp, 1e-4)));
    float behind = step(0.0, sin(a));  // the far side of the orbit: dimmer, smaller
    float body = smoothstep(size, size * 0.8, dp);
    if (fi > 4.5) {
      vec2 rq2 = d / vec2(size * 2.4, size * 0.7);
      float ring = smoothstep(1.0, 0.95, length(rq2)) * smoothstep(0.62, 0.68, length(rq2));
      o = over(o, vec3(0.9, 0.85, 0.7), ring * 0.8);
    }
    o = over(o, hue * lit * (1.0 - 0.25 * behind), body);
    o = over(o, hue, exp(-max(dp - size, 0.0) * 60.0) * 0.2);
  }
  gl_FragColor = o;
}