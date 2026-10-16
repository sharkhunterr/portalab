// Portalab — ambient/liquidmetal: the « liquidmetal » ambience (spec 028, B2)
float height(vec2 p, float t) {
  vec2 w = vec2(noise(p * 0.9 + t * 0.06), noise(p * 0.9 + vec2(5.2, -t * 0.05)));
  float h = noise(p * 1.4 + w * 2.0 + t * 0.04) * 0.75 + noise(p * 3.1 + w + t * 0.05) * 0.25;
  // drops: rings spreading and dying where something fell
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float life = 4.0 + fi * 0.7;
    float k = floor((t + fi * 1.3) / life);
    float age = fract((t + fi * 1.3) / life) * life;
    vec2 at = vec2(hash(vec2(k, fi)) * 2.6, hash(vec2(k, fi + 9.0)) * 1.0) * 1.2;
    float d = length(p - at);
    h += sin((d - age * 0.35) * 38.0) * exp(-abs(d - age * 0.35) * 14.0) * exp(-age * 0.9) * 0.08;
  }
  return h;
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  vec2 q = p * 0.85;
  float e = 0.03;
  float h = height(q, t);
  vec3 n = normalize(vec3(height(q - vec2(e, 0.0), t) - height(q + vec2(e, 0.0), t),
                          height(q - vec2(0.0, e), t) - height(q + vec2(0.0, e), t), e * 1.3));
  vec3 rf = reflect(vec3(0.0, 0.0, -1.0), n);
  vec3 env = mix(vec3(0.06, 0.065, 0.08), vec3(0.62, 0.66, 0.75), smoothstep(-0.5, 0.7, rf.y));
  env += vec3(0.9) * smoothstep(0.7, 0.98, rf.y) * smoothstep(0.35, 0.0, abs(rf.x)); // a bright strip
  env += vec3(0.5, 0.55, 0.65) * smoothstep(0.85, 1.0, abs(rf.x)) * 0.6;            // side panels
  env += vec3(1.0) * pow(max(dot(rf, normalize(vec3(0.5, 0.6, 0.62))), 0.0), 60.0) * 1.5; // a hot spot
  vec3 film = 0.5 + 0.5 * cos(6.2831 * (h * 2.0 + vec3(0.0, 0.33, 0.67)) + t * 0.2);
  float edge = pow(1.0 - n.z, 1.4);
  vec3 col = env + film * edge * 0.5;
  float a = 0.3 + edge * 0.38;
  gl_FragColor = vec4(col * a, a);
}