// Portalab — ambient/blackhole: the « blackhole » ambience (spec 028, B2)
float starField(vec2 p, float scale, float threshold) {
  vec2 g = p * scale;
  vec2 id = floor(g);
  vec2 f = fract(g) - 0.5 - (vec2(hash(id + 3.1), hash(id + 7.7)) - 0.5) * 0.6;
  return step(threshold, hash(id)) * smoothstep(0.09, 0.0, length(f)) * (0.35 + 0.65 * hash(id + 1.3));
}
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec2 c = vec2(aspect * 0.66, 0.55);
  vec2 q = p - c;
  float r = length(q);
  float R = 0.07;
  vec2 dir = q / max(r, 0.0001);
  vec4 o = vec4(0.0);
  // the sky, bent around the hole; an Einstein ring where the bending focuses it
  vec2 sky = c + dir * max(r - R * R * 2.2 / max(r, 0.001), 0.0);
  float focus = 1.0 + 2.5 * exp(-abs(r - R * 1.6) * 30.0);
  float neb = fbm(sky * 2.0 + vec2(t * 0.004, 0.0));
  o = over(o, mix(vec3(0.12, 0.05, 0.22), vec3(0.18, 0.1, 0.32), neb), smoothstep(0.45, 0.85, neb) * 0.25);
  float stars = starField(sky + vec2(t * 0.002, 0.0), 70.0, 0.984) + starField(sky * 1.7 + 3.0, 115.0, 0.99) * 0.7;
  stars *= 0.75 + 0.25 * sin(t * 2.0 + hash(floor(sky * 70.0)) * 40.0);
  o = over(o, vec3(0.9, 0.93, 1.0), clamp(stars * focus, 0.0, 1.0) * smoothstep(R * 1.05, R * 1.45, r));
  // the disc, in its tilted plane: spiral streaks, faster near the hole
  float tilt = 3.6;
  vec2 d = vec2(q.x, q.y * tilt);
  float rd = length(d);
  float ang = atan(d.y, d.x);
  float spin = t * 1.6 * pow(R / max(rd, R), 1.5);
  float spiral = ang - spin * 6.0 + log(rd) * 3.2;
  float streak = fbm(vec2(spiral * 2.4, rd * 28.0));
  float fine = noise(vec2(spiral * 14.0, rd * 90.0));
  float inner = R * 1.55;
  float band = smoothstep(inner, inner * 1.1, rd) * smoothstep(R * 5.6, inner * 2.1, rd);
  float heat = pow(clamp(inner / rd, 0.0, 1.0), 1.6);
  float facing = 0.5 + 0.5 * cos(ang + 0.35);
  float beam = 0.35 + 1.35 * facing * facing;
  vec3 disc = mix(vec3(0.82, 0.22, 0.05), vec3(1.0, 0.62, 0.25), heat);
  disc = mix(disc, vec3(1.0, 0.96, 0.88), heat * heat * beam * 0.8);
  disc *= mix(vec3(1.0), vec3(0.82, 0.92, 1.2), smoothstep(0.7, 1.5, beam));
  float density = band * (0.22 + 0.78 * streak) * (0.65 + 0.35 * fine);
  float hidden = step(0.0, q.y) * step(r, R * 1.1);
  // the far side of the disc, lensed over the top of the shadow (and a thin arc under it)
  float top = exp(-abs(r - R * 1.78) * 50.0) * smoothstep(-0.25, 0.65, dir.y);
  float bottom = exp(-abs(r - R * 1.3) * 85.0) * smoothstep(0.1, -0.6, dir.y) * 0.55;
  float arcs = (top + bottom) * (0.55 + 0.45 * fbm(vec2(atan(q.y, q.x) * 4.0 - t * 0.9, t * 0.1)));
  o = over(o, vec3(1.0, 0.7, 0.35), clamp(arcs, 0.0, 1.0) * 0.9);
  o = over(o, vec3(0.0), smoothstep(R * 1.02, R * 0.95, r));
  o = over(o, disc, clamp(density * beam * 1.25, 0.0, 1.0) * (1.0 - hidden));
  o = over(o, vec3(1.0, 0.87, 0.65), exp(-abs(r - R * 1.07) * 170.0) * 0.85);
  // stars caught: a few, at random, falling in a tightening whirl, stretched, flaring at the end
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float life = 7.0 + hash(vec2(fi, 1.0)) * 5.0;
    float k = floor((t + fi * 3.1) / life);
    float ph = fract((t + fi * 3.1) / life);
    float caught = step(0.35, hash(vec2(k, fi + 9.0)));
    float r0 = 0.32 + 0.25 * hash(vec2(k, fi + 2.0));
    float a0 = hash(vec2(k, fi + 3.0)) * 6.2831;
    float rr = mix(r0, R * 1.1, pow(ph, 1.7));
    float aa = a0 + ph * 3.0 + pow(ph, 3.0) * 11.0;
    vec2 sp = c + vec2(cos(aa), sin(aa) / tilt * 1.5) * rr;
    vec2 tang = normalize(vec2(-sin(aa), cos(aa) / tilt * 1.5));
    vec2 dd = p - sp;
    float along = dot(dd, tang);
    float across = dot(dd, vec2(-tang.y, tang.x));
    float tail = 0.004 + 0.055 * pow(ph, 3.0);
    float body = exp(-pow(across / 0.0024, 2.0))
      * exp(-pow(max(along, 0.0) / 0.004, 2.0) - pow(min(along, 0.0) / tail, 2.0));
    float flare = exp(-length(dd) * 110.0) * smoothstep(0.86, 1.0, ph);
    float fade = smoothstep(0.0, 0.1, ph) * smoothstep(1.0, 0.96, ph);
    o = over(o, vec3(0.85, 0.92, 1.0), clamp(body * 1.2 + flare, 0.0, 1.0) * fade * caught);
  }
  gl_FragColor = o;
}