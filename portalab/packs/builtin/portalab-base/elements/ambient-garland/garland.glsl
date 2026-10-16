// Portalab — ambient/garland: the « garland » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec4 o = vec4(0.0);
  o = over(o, vec3(1.0, 0.7, 0.4), smoothstep(0.55, 1.0, uv.y) * 0.05);
  for (int s = 0; s < 3; s++) {
    float fs = float(s);
    float span = 0.55 + fs * 0.1;
    float top = 0.95 - fs * 0.13;
    float sag = 0.07 + 0.02 * fs;
    float sway = 1.0 + 0.08 * sin(t * 0.6 + fs * 1.7);
    float x = p.x / span + fs * 0.37;
    float xf = fract(x);
    float y0 = top - sag * sway * 4.0 * xf * (1.0 - xf);
    float twist = sin(p.x * 260.0) * 0.0014;
    float wire = max(smoothstep(0.0018, 0.0, abs(uv.y - y0 - twist)), smoothstep(0.0018, 0.0, abs(uv.y - y0 + twist)));
    o = over(o, vec3(0.05, 0.1, 0.06), wire * 0.85);
    float n = 9.0;
    float bi0 = floor(xf * n);
    for (int b = -1; b <= 1; b++) {
      float bi = bi0 + float(b);
      float bx = (bi + 0.5) / n;
      float id = floor(x) * 10.0 + bi + fs * 100.0;
      float by = top - sag * sway * 4.0 * bx * (1.0 - bx);
      vec2 d = vec2((xf - bx) * span, uv.y - by);
      float ang = sin(t * 1.3 + id) * 0.12;
      d = mat2(cos(ang), -sin(ang), sin(ang), cos(ang)) * d;
      float pick = floor(hash(vec2(id, 2.0)) * 5.0);
      vec3 hue = pick < 1.0 ? vec3(1.0, 0.18, 0.15) : pick < 2.0 ? vec3(0.2, 0.9, 0.35) : pick < 3.0 ? vec3(0.25, 0.5, 1.0) : pick < 4.0 ? vec3(1.0, 0.68, 0.2) : vec3(0.95, 0.3, 0.85);
      float chase = smoothstep(0.2, 1.0, sin((x - bx + bi / n) * 6.2831 * 1.5 - t * 2.2 + fs * 2.0));
      float tw = 0.75 + 0.25 * sin(t * (1.5 + hash(vec2(id, 1.0)) * 3.0) + id);
      float out_ = step(0.96, hash(vec2(id, floor(t * 0.4))));
      float lit = (0.45 + 0.55 * chase) * tw * (1.0 - out_ * 0.85);
      float socket = smoothstep(0.0012, 0.0, abs(d.x) - 0.0032) * step(-0.011, d.y) * step(d.y, 0.0);
      vec2 g = (d - vec2(0.0, -0.022)) / vec2(0.0078, 0.0135);
      g.x *= 1.0 + 0.25 * clamp(-g.y, 0.0, 1.0);
      float glass = smoothstep(1.0, 0.85, length(g));
      float core = exp(-length(g * vec2(1.4, 1.0)) * 3.0);
      float spec = smoothstep(0.32, 0.12, length(g - vec2(-0.4, 0.35)));
      float r = length(d - vec2(0.0, -0.022));
      o = over(o, hue, exp(-r * 13.0) * 0.07 * lit);
      o = over(o, hue, exp(-r * 48.0) * 0.5 * lit);
      o = over(o, vec3(0.06, 0.12, 0.07), socket);
      vec3 col = mix(hue * (0.35 + 0.65 * lit), mix(hue, vec3(1.0, 0.95, 0.85), 0.6), core * lit);
      o = over(o, col, glass * (0.75 + 0.25 * lit));
      o = over(o, vec3(1.0), spec * glass * 0.7);
    }
  }
  gl_FragColor = o;
}