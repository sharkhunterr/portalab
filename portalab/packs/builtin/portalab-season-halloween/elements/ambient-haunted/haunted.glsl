// Portalab — ambient/haunted: the « haunted » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  float beat = mod(t, 1.6);
  float pulse = exp(-beat * 9.0) + 0.7 * exp(-abs(beat - 0.28) * 12.0);
  vec2 c = uv - 0.5;
  float vignette = smoothstep(0.12 - pulse * 0.06, 0.72, length(c * vec2(1.25, 1.0)));
  o = over(o, vec3(0.02, 0.0, 0.01), vignette * 0.95);
  float pass = mod(t, 13.0) / 4.0;
  o = over(o, vec3(0.0), step(pass, 1.0) * smoothstep(0.35, 0.0, abs(uv.x - (pass * 1.6 - 0.3))) * 0.45);
  float k = floor(t * 12.0);
  float failing = step(0.86, hash(vec2(k, 1.0))) * step(0.5, hash(vec2(floor(t * 0.7), 2.0)));
  o = over(o, vec3(0.75, 0.8, 0.7), failing * 0.14);
  o = over(o, vec3(0.0), (1.0 - failing) * step(0.97, hash(vec2(k, 3.0))) * 0.35);
  // the figure: near or far, appearing, swaying, flickering like a bad reception, fading
  float slot = floor(t / 11.0);
  float ph = mod(t, 11.0);
  float seen = step(0.4, hash(vec2(slot, 4.0))) * smoothstep(1.5, 3.2, ph) * smoothstep(7.0, 5.2, ph);
  seen *= 0.75 + 0.25 * step(0.25, hash(vec2(floor(t * 9.0), 6.0)));
  float scale = 0.8 + 0.6 * hash(vec2(slot, 7.0));
  vec2 at = vec2(aspect * (0.12 + 0.76 * hash(vec2(slot, 5.0))), 0.06);
  vec2 f = (p - at) / scale;
  f.x -= sin(t * 0.7 + f.y * 6.0) * 0.004 * f.y * 4.0;
  float fray = (noise(vec2(f.y * 34.0, t * 0.9)) - 0.5) * 0.012 + (noise(vec2(f.x * 60.0, t)) - 0.5) * 0.02 * smoothstep(0.08, 0.0, f.y);
  float w = mix(0.062, 0.043, clamp(f.y / 0.24, 0.0, 1.0)) + fray;
  float torso = smoothstep(0.008, 0.0, abs(f.x) - w) * smoothstep(0.262, 0.248, f.y + f.x * f.x * 9.0) * step(0.0, f.y);
  float neck = smoothstep(0.004, 0.0, abs(f.x) - 0.011) * step(0.2, f.y) * step(f.y, 0.29);
  vec2 hd = (f - vec2(0.0, 0.305)) / vec2(0.022, 0.029);
  float head = smoothstep(1.0, 0.8, length(hd));
  float hollow = smoothstep(0.32, 0.18, length(vec2(abs(hd.x) - 0.38, hd.y - 0.05) * vec2(1.0, 1.4)));
  float shape = clamp(torso + neck + head, 0.0, 1.0);
  float inner = 0.55 + 0.45 * fbm(vec2(f.x * 30.0, f.y * 12.0 - t * 0.4));
  float figure = shape * inner * smoothstep(0.0, 0.1, f.y);
  float halo = exp(-length((f - vec2(0.0, 0.18)) / vec2(0.09, 0.18)) * 2.5) * 0.25;
  o = over(o, vec3(0.62, 0.7, 0.78), (figure * 0.42 + halo) * seen);
  o = over(o, vec3(0.0), hollow * head * seen * 0.6);
  // fog creeping low, slow — over the figure's feet
  float fog = fbm(vec2(p.x * 1.4 + t * 0.03, uv.y * 3.5 - t * 0.015) + fbm(p * 2.0 + t * 0.02));
  fog *= smoothstep(0.55, 0.0, uv.y);
  o = over(o, vec3(0.55, 0.6, 0.62), smoothstep(0.3, 0.8, fog) * 0.7);
  o = over(o, vec3(0.35, 0.0, 0.02), pulse * vignette * 0.18);
  gl_FragColor = o;
}