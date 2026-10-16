// Portalab — ambient/popwatercolor: the « popwatercolor » ambience (spec 028, B2)
vec3 paintColour(float x) {
  x = fract(x);
  vec3 c0 = vec3(0.55, 0.2, 0.95);
  vec3 c1 = vec3(1.0, 0.18, 0.55);
  vec3 c2 = vec3(1.0, 0.55, 0.1);
  vec3 c3 = vec3(1.0, 0.86, 0.15);
  vec3 c4 = vec3(0.1, 0.82, 0.8);
  float b = 0.035;
  vec3 c = mix(c0, c1, smoothstep(0.2 - b, 0.2 + b, x));
  c = mix(c, c2, smoothstep(0.4 - b, 0.4 + b, x));
  c = mix(c, c3, smoothstep(0.6 - b, 0.6 + b, x));
  c = mix(c, c4, smoothstep(0.8 - b, 0.8 + b, x));
  return mix(c, c0, smoothstep(0.96, 1.0, x));
}
float edgeOf(vec2 uv) {
  return smoothstep(0.18, 0.62, length((uv - 0.5) * vec2(1.25, 1.0)));
}

void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  float paper = 0.9 + 0.1 * noise(p * 300.0);
  o = over(o, vec3(0.98, 0.9, 0.78), 0.035 * paper);
  for (int i = 0; i < 9; i++) {
    float fi = float(i);
    float life = 14.0 + 8.0 * hash(vec2(fi, 1.0));
    float tt = t + hash(vec2(fi, 2.0)) * life;
    float slot = floor(tt / life);
    float ph = fract(tt / life);
    vec2 c = vec2(aspect * hash(vec2(slot, fi + 3.0)), hash(vec2(slot, fi + 4.0)));
    float r = (0.2 + 0.25 * hash(vec2(slot, fi + 5.0))) * (1.0 - pow(1.0 - min(ph * 1.6, 1.0), 3.0));
    vec2 d = p - c;
    float a = atan(d.y, d.x);
    vec2 dir = vec2(cos(a), sin(a));
    float wobble = 0.6 + 0.5 * noise(dir * 1.6 + vec2(fi * 3.0 + slot, 0.0)) + 0.12 * noise(dir * 5.0 + d * 4.0 + fi);
    float dist = length(d) / max(r * wobble, 1e-3);
    float inside = smoothstep(1.0, 0.85, dist);
    float rim = smoothstep(0.82, 0.98, dist) * inside;
    float grain = 0.88 + 0.12 * noise(p * 90.0 + fi);
    float bleed = 0.6 + 0.4 * fbm(d * 6.0 + fi);
    float fade = smoothstep(1.0, 0.7, ph);
    vec3 col = paintColour(hash(vec2(slot, fi + 6.0)) * 0.95);
    o = over(o, col * grain, (inside * 0.26 * bleed + rim * 0.24) * fade * (0.7 + 0.6 * edgeOf(uv)));
  }
  gl_FragColor = o;
}