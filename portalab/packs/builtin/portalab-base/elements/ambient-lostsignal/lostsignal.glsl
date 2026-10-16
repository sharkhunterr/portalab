// Portalab — ambient/lostsignal: the « lostsignal » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  float wobble = (noise(vec2(uv.y * 6.0, t * 4.0)) - 0.5) * 0.004;
  float grain = hash(floor(gl_FragCoord.xy * 0.6) + floor(t * 24.0) * 17.0);
  o = over(o, vec3(grain), 0.2);
  float jitter = step(0.96, hash(vec2(floor(gl_FragCoord.y / 3.0), floor(t * 15.0))));
  o = over(o, vec3(0.85), jitter * 0.3);
  float roll = fract(t * 0.11);
  float near = exp(-abs(uv.y - (1.0 - roll)) * 60.0);
  float lines = step(0.5, fract(gl_FragCoord.y * 0.5)) * 0.06;
  o = over(o, vec3(0.9), near * 0.5 + lines * 0.5);
  float shift = near * (hash(vec2(floor(t * 20.0), uv.y)) - 0.5) + wobble * 30.0;
  o = over(o, vec3(1.0, 0.1, 0.2), smoothstep(0.0, 0.3, abs(shift)) * 0.22);
  o = over(o, vec3(0.1, 0.9, 1.0), smoothstep(0.0, 0.3, abs(shift * 1.3)) * 0.16);
  // the head-switching band at the bottom of a worn tape
  float bottom = step(uv.y, 0.035);
  float smear = hash(vec2(floor(gl_FragCoord.y), floor(t * 30.0))) * 0.6 + 0.2;
  o = over(o, vec3(smear), bottom * 0.55);
  // REC, blinking in the corner
  vec2 rec = vec2(0.06 * aspect, 0.93);
  float dot_ = smoothstep(0.012, 0.009, length(vec2((p.x - rec.x), uv.y - rec.y)));
  o = over(o, vec3(1.0, 0.1, 0.1), dot_ * step(0.5, fract(t * 0.8)));
  vec2 c = uv - 0.5;
  o = over(o, vec3(0.0), smoothstep(0.3, 0.72, length(c)) * 0.75);
  float cut = step(0.93, hash(vec2(floor(t * 1.5), 7.0)));
  o = over(o, vec3(0.0), cut * 0.75);
  gl_FragColor = o;
}