// Brick rain HD — an ambience behind the whole portal (u_res, u_time, hash, noise, fbm, over): bricks of the
// primary colours falling in their columns, turning a little, landing on a green studded plate at the bottom
// where a low wall grows, then is cleared; see-through above, never under the middle of the page.
void main() {
  vec2 uv = gl_FragCoord.xy / u_res;
  float aspect = u_res.x / u_res.y;
  vec2 c = vec2(uv.x * aspect, uv.y);
  float t = u_time;
  vec4 o = vec4(0.0);
  float plate = 0.03;
  o = over(o, vec3(0.16, 0.6, 0.29) * (0.85 + 0.15 * step(0.5, fract(c.x * 60.0))), step(uv.y, plate) * 0.75);
  float stud = step(uv.y, plate + 0.006) * step(plate, uv.y) * step(0.25, fract(c.x * 60.0)) * step(fract(c.x * 60.0), 0.75);
  o = over(o, vec3(0.22, 0.7, 0.36), stud * 0.75);
  for (int k = 0; k < 16; k++) {
    float fk = float(k);
    float col = (fk + 0.5) / 16.0 * aspect;
    float speed = 0.05 + 0.04 * hash(vec2(fk, 1.0));
    float cyc = t * speed + hash(vec2(fk, 2.0));
    float fall = fract(cyc);
    float landed = plate + 0.012 + 0.024 * mod(floor(cyc), 4.0);
    float y = mix(1.05, landed, smoothstep(0.0, 0.85, fall));
    float bounce = 0.006 * abs(sin(fall * 40.0)) * smoothstep(0.85, 0.9, fall) * smoothstep(1.0, 0.9, fall);
    vec2 q = c - vec2(col + 0.01 * sin(t + fk), y + bounce);
    float ang = 0.4 * sin(t * 0.7 + fk) * smoothstep(0.85, 0.5, fall);
    q = mat2(cos(ang), -sin(ang), sin(ang), cos(ang)) * q;
    float body = step(abs(q.x), 0.026) * step(abs(q.y), 0.011);
    float studs = step(0.011, q.y) * step(q.y, 0.016) * step(abs(q.x), 0.026) * step(0.5, fract(q.x / 0.026 + 0.25));
    float h = hash(vec2(fk, floor(cyc)));
    vec3 bc = h < 0.25 ? vec3(0.84, 0.16, 0.16) : (h < 0.5 ? vec3(0.97, 0.77, 0.12) : (h < 0.75 ? vec3(0.12, 0.44, 0.84) : vec3(0.96, 0.96, 0.94)));
    bc *= 0.8 + 0.35 * smoothstep(-0.011, 0.011, q.y);
    float edge = 0.35 + 0.65 * smoothstep(0.2, 0.45, abs(uv.x - 0.5)) + 0.65 * smoothstep(0.35, 0.05, uv.y);
    edge = min(edge, 1.0);
    o = over(o, bc, clamp(body + studs, 0.0, 1.0) * 0.55 * edge);
  }
  gl_FragColor = o;
}
