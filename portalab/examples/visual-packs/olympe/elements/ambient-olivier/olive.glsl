// Gold dust and olive leaves — an ambience behind the whole portal (u_res, u_time, hash, noise, fbm, over): a
// soft sunbeam slanting from the top corner, specks of gold floating in it, olive leaves drifting down and
// turning. Light and mostly see-through, made for a bright interface.
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  float aspect = u_res.x / u_res.y;
  vec2 c = vec2(uv.x * aspect, uv.y);
  float t = u_time;
  vec4 o = vec4(0.0);
  float beam = smoothstep(0.25, 0.0, abs((c.x - aspect * 0.15) - (1.0 - uv.y) * 0.6) - 0.1 * (1.0 - uv.y));
  o = over(o, vec3(1.0, 0.9, 0.6), beam * 0.12);
  for (int k = 0; k < 40; k++) {
    float fk = float(k);
    vec2 at = vec2(fract(hash(vec2(fk, 1.0)) + 0.01 * sin(t * 0.3 + fk)) * aspect, fract(hash(vec2(fk, 2.0)) + t * 0.008 * (0.5 + hash(vec2(fk, 3.0)))));
    float tw = 0.5 + 0.5 * sin(t * 2.0 + fk * 1.7);
    o = over(o, vec3(0.85, 0.65, 0.2), exp(-length(c - at) * 500.0) * tw * 0.8);
  }
  for (int k = 0; k < 7; k++) {
    float fk = float(k);
    float fall = fract(t * (0.025 + 0.01 * hash(vec2(fk, 4.0))) + hash(vec2(fk, 5.0)));
    vec2 at = vec2(hash(vec2(fk, 6.0)) * aspect + 0.06 * sin(fall * 12.0 + fk), 1.05 - fall * 1.1);
    float ang = fall * 9.0 + fk;
    vec2 q = c - at;
    q = mat2(cos(ang), -sin(ang), sin(ang), cos(ang)) * q;
    float leaf = smoothstep(1.0, 0.85, length(q / vec2(0.022, 0.007)));
    o = over(o, mix(vec3(0.35, 0.45, 0.25), vec3(0.55, 0.62, 0.4), step(0.0, q.y)), leaf * 0.55);
  }
  gl_FragColor = o;
}
