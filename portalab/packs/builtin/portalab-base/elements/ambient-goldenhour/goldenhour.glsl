// Portalab — ambient/goldenhour: the « goldenhour » ambience (spec 028, B2)
void main() {
  vec2 uv;
  vec2 p = coords(uv);
  float t = u_time;
  float aspect = u_res.x / u_res.y;
  vec4 o = vec4(0.0);
  vec2 sun = vec2(aspect * 0.9, 0.98);
  vec2 d = p - sun;
  float r = length(d);
  o = over(o, vec3(1.0, 0.6, 0.25), 0.05 + 0.24 * exp(-r * 1.4));
  float a = atan(d.x, -d.y);
  float rays = pow(noise(vec2(a * 18.0 + t * 0.04, t * 0.07)), 2.5) * 0.7 + pow(noise(vec2(a * 41.0 - t * 0.03, 3.0 + t * 0.05)), 3.0) * 0.5;
  o = over(o, vec3(1.0, 0.78, 0.45), rays * exp(-r * 0.9) * 0.3);
  // light through leaves swaying in the breeze
  vec2 sway = vec2(sin(t * 0.4), cos(t * 0.33)) * 0.03;
  float leaves = fbm(p * 3.2 + sway + vec2(t * 0.01, 0.0));
  float spots = smoothstep(0.58, 0.66, leaves) * smoothstep(1.6, 0.3, r);
  o = over(o, vec3(1.0, 0.82, 0.5), spots * 0.12);
  o = over(o, vec3(1.0, 0.95, 0.8), exp(-r * 9.0) * 0.8);
  // lens flares on the line from the sun through the middle
  vec2 axis = vec2(aspect * 0.5, 0.5) - sun;
  for (int i = 0; i < 5; i++) {
    float fi = float(i);
    vec2 g = sun + axis * (0.45 + fi * 0.38);
    float rad = 0.02 + 0.03 * hash(vec2(fi, 1.0)) + fi * 0.006;
    float dg = length(p - g);
    vec3 tint = fi == 1.0 ? vec3(0.5, 0.9, 0.7) : fi == 3.0 ? vec3(0.7, 0.6, 1.0) : vec3(1.0, 0.7, 0.4);
    float disc = smoothstep(rad, rad * 0.85, dg) * 0.05 + smoothstep(0.004, 0.0, abs(dg - rad)) * 0.06;
    o = over(o, tint, disc * (0.8 + 0.2 * sin(t * 0.5 + fi)));
  }
  // bokeh, rising slowly
  for (int i = 0; i < 12; i++) {
    float fi = float(i);
    float sp = 0.01 + 0.02 * hash(vec2(fi, 3.0));
    vec2 b = vec2(aspect * hash(vec2(fi, 4.0)) + sin(t * 0.2 + fi) * 0.05, fract(hash(vec2(fi, 5.0)) + t * sp) * 1.3 - 0.15);
    float rad = 0.025 + 0.05 * hash(vec2(fi, 6.0));
    float db = length(p - b);
    float shape = smoothstep(rad, rad * 0.8, db);
    float edge = smoothstep(rad * 0.7, rad, db) * shape;
    vec3 col = mix(vec3(1.0, 0.7, 0.35), vec3(1.0, 0.9, 0.6), hash(vec2(fi, 7.0)));
    o = over(o, col, (shape * 0.05 + edge * 0.07) * (0.6 + 0.4 * sin(t * 0.7 + fi * 2.0)));
  }
  gl_FragColor = o;
}