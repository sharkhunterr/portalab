// Portalab — ambient/hearth: the « hearth » ambience (spec 028, B2)
float capsule(vec2 p, vec2 a, vec2 b, float r) {
  vec2 pa = p - a;
  vec2 ba = b - a;
  float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
  return length(pa - ba * h) - r;
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  float cx = aspect * 0.5;
  float flicker = 0.8 + 0.12 * sin(t * 1.7) + 0.08 * (noise(vec2(t * 6.0, 0.0)) - 0.5) * 2.0;
  // the warm light of the fire over the whole room
  o = over(o, vec3(1.0, 0.5, 0.15), (0.04 + 0.05 * smoothstep(0.8, 0.0, uv.y)) * flicker);
  float hx = (p.x - cx) / (aspect * 0.42);
  float env = exp(-hx * hx * 1.6);
  o = over(o, vec3(0.95, 0.4, 0.08), smoothstep(0.55, 0.0, uv.y) * (0.12 + 0.2 * env) * flicker);
  // the flames: rising tongues, a blue foot, a white-hot heart
  vec2 q = vec2(p.x * 5.0, p.y * 3.2 - t * 1.9);
  float n = fbm(q + vec2(fbm(q * 1.6 - vec2(0.0, t * 0.9)), 0.0) * 1.3);
  float tongues = 0.5 + 0.5 * sin(p.x * 22.0 + noise(vec2(p.x * 3.0, t)) * 6.0);
  float env2 = env * env;
  float height = (0.025 + 0.27 * env2) * (0.7 + 0.5 * tongues) * (0.8 + 0.25 * noise(vec2(p.x * 2.0, t * 1.3)));
  float f = clamp((1.0 - (uv.y - 0.02) / height) * (0.6 + 0.5 * env2) + (n - 0.55) * 1.6, 0.0, 1.0);
  f *= smoothstep(0.0, 0.03, uv.y + 0.01);
  vec3 fc = mix(vec3(0.7, 0.12, 0.02), vec3(1.0, 0.5, 0.08), smoothstep(0.1, 0.5, f));
  fc = mix(fc, vec3(1.0, 0.85, 0.45), smoothstep(0.55, 0.85, f));
  fc = mix(fc, vec3(1.0, 0.97, 0.85), smoothstep(0.9, 1.0, f) * env2);
  float blue = smoothstep(0.07, 0.035, uv.y) * smoothstep(0.02, 0.04, uv.y) * smoothstep(0.3, 0.6, f) * env;
  fc = mix(fc, vec3(0.3, 0.45, 1.0), blue * 0.5);
  o = over(o, fc, smoothstep(0.05, 0.45, f) * (0.55 + 0.37 * env));
  // the logs, crossed in the middle, charred, glowing in their cracks
  float logs = 1e3;
  logs = min(logs, capsule(p, vec2(cx - 0.32, 0.025), vec2(cx + 0.08, 0.06), 0.024));
  logs = min(logs, capsule(p, vec2(cx + 0.34, 0.022), vec2(cx - 0.06, 0.065), 0.026));
  logs = min(logs, capsule(p, vec2(cx - 0.12, 0.012), vec2(cx + 0.16, 0.014), 0.02));
  float wood = smoothstep(0.002, -0.002, logs);
  float crack = 1.0 - abs(2.0 * fbm(p * vec2(30.0, 60.0) + vec2(0.0, t * 0.05)) - 1.0);
  float ember = smoothstep(0.93, 0.99, crack) * (0.5 + 0.5 * sin(t * 2.0 + p.x * 30.0));
  float bark = 0.7 + 0.3 * noise(p * vec2(60.0, 200.0));
  float rimLight = smoothstep(-0.012, 0.0, logs) * step(0.03, p.y);
  vec3 woodc = mix(vec3(0.09, 0.045, 0.025) * bark, vec3(1.0, 0.45, 0.08), ember);
  woodc += vec3(0.5, 0.18, 0.03) * rimLight * flicker;
  o = over(o, woodc, wood);
  // the bed of embers along the bottom, breathing
  float bed = smoothstep(0.03, 0.0, uv.y) * smoothstep(0.35, 0.75, noise(vec2(p.x * 40.0, t * 0.8))) * (0.25 + 0.75 * env);
  o = over(o, vec3(1.0, 0.35, 0.05), bed * 0.8);
  // frost at the corners: fine branching crystals, a misted pane
  vec2 cc = min(uv, 1.0 - uv) * vec2(aspect, 1.0);
  float corner = length(cc);
  float grow = 0.18 + 0.03 * sin(t * 0.15);
  float reach = smoothstep(grow, grow * 0.3, corner + (fbm(p * 6.0) - 0.5) * 0.08);
  o = over(o, vec3(0.75, 0.85, 0.95), reach * 0.1);
  float branch = 1.0 - abs(2.0 * fbm(p * 18.0 + fbm(p * 7.0) * 1.5) - 1.0);
  float twig = 1.0 - abs(2.0 * fbm(p * 48.0 + 5.0) - 1.0);
  float lines = smoothstep(0.97, 0.997, branch) + 0.4 * smoothstep(0.975, 0.998, twig);
  o = over(o, vec3(0.9, 0.96, 1.0), lines * reach * 0.45 * (1.0 - smoothstep(0.4, 0.0, uv.y) * 0.6));
  gl_FragColor = o;
}