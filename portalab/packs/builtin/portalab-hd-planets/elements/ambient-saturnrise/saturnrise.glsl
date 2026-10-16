// Portalab — ambient/saturnrise: the « saturnrise » ambience (spec 028, B2)
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
  o = over(o, vec3(1.0, 0.97, 0.9), starfield(p, 90.0, t, 0.03));
  vec2 ctr = vec2(0.8 * aspect, -0.05);
  float R = 0.55;
  vec2 c = p - ctr;
  float tilt = -0.28;
  vec2 q = mat2(cos(tilt), -sin(tilt), sin(tilt), cos(tilt)) * c;
  float r = length(c);
  float lat = q.y / R;
  float bands = sin(lat * 18.0 + fbm(vec2(q.x * 2.5 - t * 0.02, lat * 5.0)) * 2.5);
  vec3 planet = mix(vec3(0.72, 0.55, 0.35), vec3(0.97, 0.88, 0.68), 0.5 + 0.5 * bands);
  planet = mix(planet, vec3(0.6, 0.4, 0.25), smoothstep(0.55, 0.85, fbm(vec2(q.x * 4.0 - t * 0.03, lat * 12.0))) * 0.4);
  float z = sqrt(max(0.0, 1.0 - dot(c, c) / (R * R)));
  vec3 n = vec3(c / R, z);
  float light = clamp(dot(n, normalize(vec3(-0.7, 0.5, 0.5))), 0.0, 1.0);
  planet *= 0.12 + 0.95 * light;
  vec2 rq = vec2(q.x, q.y * 4.6) / R;
  float rr = length(rq);
  float ring = smoothstep(1.25, 1.28, rr) * smoothstep(2.25, 2.2, rr);
  ring *= 0.55 + 0.45 * sin(rr * 45.0) * sin(rr * 11.0 + 1.0);
  ring *= 1.0 - 0.9 * smoothstep(1.8, 1.83, rr) * smoothstep(1.9, 1.87, rr);
  vec3 rcol = mix(vec3(0.75, 0.68, 0.55), vec3(1.0, 0.95, 0.85), smoothstep(1.3, 2.2, rr)) * (0.45 + 0.55 * smoothstep(-0.6, 0.4, -q.x / R));
  float inside = smoothstep(R + 0.004, R - 0.004, r);
  float front = step(q.y, 0.0);
  float shadow = smoothstep(0.03, 0.0, abs(q.y - 0.06)) * 0.0 + smoothstep(R * 0.24, R * 0.16, abs(q.y + 0.02 - q.x * 0.0)) * step(0.0, q.x) * 0.35;
  o = over(o, vec3(0.95, 0.8, 0.55), exp(-max(r - R, 0.0) * 9.0) * 0.18 * step(R, r));
  o = over(o, rcol, ring * (1.0 - front) * (1.0 - inside) * 0.9);
  o = over(o, planet * (1.0 - shadow), inside);
  o = over(o, rcol, ring * front * 0.92);
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float a = t * (0.08 + 0.05 * fi) + fi * 2.0;
    vec2 at = ctr + mat2(cos(tilt), sin(tilt), -sin(tilt), cos(tilt)) * vec2(cos(a) * R * (2.5 + 0.5 * fi), sin(a) * R * (2.5 + 0.5 * fi) / 4.6);
    float hidden = step(0.0, sin(a)) * inside;
    o = over(o, vec3(0.85, 0.85, 0.9), smoothstep(0.012, 0.008, length(p - at)) * (1.0 - hidden));
  }
  gl_FragColor = o;
}