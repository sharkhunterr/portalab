// Portalab — ambient/pixelballoons: the « pixelballoons » ambience (spec 028, B2)
float bayer2(vec2 a) {
  a = floor(a);
  return fract(dot(a, vec2(0.5, a.y * 0.75)));
}
float bayer4(vec2 a) {
  return bayer2(0.5 * a) * 0.25 + bayer2(a);
}
// a two-colour gradient the old way: v from 0 to 1 picks a or b, the dither mixing them in between
vec3 dither(vec3 a, vec3 b, float v, vec2 px) {
  return step(bayer4(px), clamp(v, 0.0, 1.0)) > 0.5 ? b : a;
}

void main() {
  float rows = 180.0;
  vec2 px = floor(gl_FragCoord.xy / u_res.y * rows);
  float W = floor(u_res.x / u_res.y * rows);
  float t = u_time;
  vec4 o = vec4(0.0);
  o = over(o, dither(vec3(0.62, 0.82, 1.0), vec3(0.36, 0.6, 0.95), (px.y - 40.0) / 140.0, px), 0.5);
  // the sun and its turning rays
  vec2 sun = vec2(floor(W * 0.88), 155.0);
  vec2 sd = px - sun;
  float sa = atan(sd.y, sd.x) + floor(t * 4.0) * 0.06;
  float rays = step(length(sd), 18.0) * step(12.0, length(sd)) * step(0.5, fract(sa * 8.0 / 6.2831));
  o = over(o, vec3(1.0, 0.88, 0.35), clamp(step(length(sd), 9.0) + rays, 0.0, 1.0));
  // puffy clouds made of round blobs, drifting
  for (int i = 0; i < 5; i++) {
    float fi = float(i);
    float cx = mod(hash(vec2(fi, 1.0)) * W + t * (2.0 + fi), W + 60.0) - 30.0;
    vec2 c = vec2(floor(cx), floor(95.0 + 70.0 * hash(vec2(fi, 2.0))));
    vec2 q = px - c;
    float cl = max(max(step(length(q), 7.0), step(length(q - vec2(8.0, -2.0)), 6.0)), max(step(length(q - vec2(-8.0, -2.0)), 5.0), step(length(q - vec2(15.0, -4.0)), 4.0)));
    cl = max(cl, step(abs(q.x - 3.0), 17.0) * step(abs(q.y + 5.0), 2.0));
    float shade = step(q.y, -5.0);
    o = over(o, shade > 0.5 ? vec3(0.78, 0.86, 0.98) : vec3(1.0), cl * 0.95);
  }
  // the hills: far green, near patchwork
  float h1 = 52.0 + floor(10.0 * sin(px.x * 0.02 + 1.0) + 5.0 * sin(px.x * 0.05));
  o = over(o, vec3(0.45, 0.72, 0.4), step(px.y, h1));
  float h2 = 34.0 + floor(8.0 * sin(px.x * 0.015 + 3.0) + 4.0 * sin(px.x * 0.043 + 1.0));
  vec2 fq = floor(vec2(px.x + px.y * 1.5, px.y) / vec2(22.0, 7.0));
  float fh = hash(fq);
  vec3 fc = fh < 0.3 ? vec3(0.95, 0.82, 0.35) : fh < 0.6 ? vec3(0.4, 0.7, 0.3) : fh < 0.8 ? vec3(0.55, 0.8, 0.35) : vec3(0.75, 0.55, 0.32);
  vec2 fr = mod(vec2(px.x + px.y * 1.5, px.y), vec2(22.0, 7.0));
  fc = (fr.x < 1.0 || fr.y < 1.0) ? vec3(0.22, 0.45, 0.22) : fc;
  o = over(o, dither(fc, fc * 0.88, hash(floor(px / 2.0)) * 0.5, px), step(px.y, h2));
  // little houses on the far hill
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float hx = floor(W * (0.12 + fi * 0.22 + 0.05 * hash(vec2(fi, 3.0))));
    float hb = 52.0 + floor(10.0 * sin(hx * 0.02 + 1.0) + 5.0 * sin(hx * 0.05)) - 1.0;
    vec2 q = px - vec2(hx, hb);
    float wall = step(abs(q.x), 3.0) * step(0.0, q.y) * step(q.y, 4.0);
    float roof = step(5.0, q.y) * step(abs(q.x), 4.0 - (q.y - 5.0)) * step(q.y, 8.0);
    o = over(o, vec3(1.0, 0.95, 0.85), wall);
    o = over(o, vec3(0.85, 0.2, 0.15), roof);
    o = over(o, vec3(0.35, 0.25, 0.2), wall * step(abs(q.x - 1.0), 0.5) * step(q.y, 2.0));
  }
  // the windmill, its sails turning
  vec2 wm = vec2(floor(W * 0.72), 0.0);
  wm.y = 52.0 + floor(10.0 * sin(wm.x * 0.02 + 1.0) + 5.0 * sin(wm.x * 0.05));
  vec2 wq = px - wm;
  float tower = step(0.0, wq.y) * step(wq.y, 18.0) * step(abs(wq.x), 4.0 - wq.y * 0.12);
  o = over(o, vec3(0.95, 0.92, 0.85), tower);
  vec2 hub = wq - vec2(0.0, 18.0);
  float wa = floor(t * 6.0) * 0.12;
  float sails = 0.0;
  for (int i = 0; i < 4; i++) {
    float a = wa + float(i) * 1.5708;
    vec2 dir = vec2(cos(a), sin(a));
    float along = dot(hub, dir);
    float across = abs(dot(hub, vec2(-dir.y, dir.x)) - 1.5);
    sails += step(0.0, along) * step(along, 14.0) * step(across, 1.6);
  }
  o = over(o, vec3(0.55, 0.35, 0.25), clamp(sails, 0.0, 1.0));
  o = over(o, vec3(0.3, 0.2, 0.15), step(length(hub), 1.6));
  // the balloons: striped envelopes, ropes, baskets, a burner puffing now and then
  for (int i = 0; i < 5; i++) {
    float fi = float(i);
    float R = 8.0 + floor(8.0 * hash(vec2(fi, 4.0)));
    float rise = fract(hash(vec2(fi, 5.0)) + t * (0.006 + 0.006 * hash(vec2(fi, 6.0))));
    vec2 c = vec2(floor(mod(W * hash(vec2(fi, 7.0)) + t * (1.5 + fi * 0.6), W + 40.0) - 20.0),
                  floor(40.0 + rise * 170.0 + 2.0 * sin(t * 0.8 + fi)));
    vec2 q = px - c;
    float env = step(length(q * vec2(1.0, 0.9)), R) + step(abs(q.x), R * 0.55 * (1.0 + q.y / R)) * step(-R * 1.3, q.y) * step(q.y, 0.0);
    env = clamp(env, 0.0, 1.0);
    float stripe = mod(floor((q.x / R + 1.0) * 3.0), 2.0);
    float pick = hash(vec2(fi, 8.0));
    vec3 ca = pick < 0.33 ? vec3(0.95, 0.3, 0.3) : pick < 0.66 ? vec3(0.3, 0.55, 0.95) : vec3(0.98, 0.75, 0.2);
    vec3 cb = pick < 0.5 ? vec3(1.0, 0.95, 0.85) : vec3(0.35, 0.8, 0.5);
    vec3 col = stripe > 0.5 ? ca : cb;
    col *= q.x > R * 0.45 ? 0.8 : 1.0;
    col = length(q - vec2(-R * 0.4, R * 0.45)) < R * 0.18 ? vec3(1.0) : col;
    o = over(o, col, env);
    float basketY = -R * 1.3 - 6.0;
    float ropes = step(abs(abs(q.x) - 2.0 - (q.y - basketY) * 0.1), 0.5) * step(basketY + 3.0, q.y) * step(q.y, -R * 1.3);
    float basket = step(abs(q.x), 2.5) * step(abs(q.y - basketY), 1.5);
    float burn = step(0.85, hash(vec2(fi, floor(t * 3.0)))) * step(abs(q.x), 1.0) * step(abs(q.y - basketY - 5.0), 1.0);
    o = over(o, vec3(0.35, 0.25, 0.2), ropes);
    o = over(o, vec3(0.6, 0.38, 0.2), basket);
    o = over(o, vec3(1.0, 0.65, 0.2), burn);
  }
  gl_FragColor = o;
}