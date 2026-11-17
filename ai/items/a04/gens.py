"""템플릿 위치와 변위의 조건을 바꿈."""
from aiprep.gen import gen, blank

@gen("a04-g01", unit="a4a", level=2, tags=["app.a4a"], ref=["응용 4차시 노트북 01 [3]"], facts=["FA04-a"], basis="lecture-formula", step="a4a/2")
def template_shape(r):
    h, w = r.int(8, 30), r.int(10, 40)
    th, tw = r.int(2, 6), r.int(2, 8)
    return blank(stem=f"높이 {h}·너비 {w} 영상과 높이 {th}·너비 {tw} 템플릿의 점수 지도 shape는 ____ 입니다.", blanks=[{"answer":[str((h-th+1,w-tw+1))],"mode":"shape"}], explain=f"세로 {h}−{th}+1={h-th+1}, 가로 {w}−{tw}+1={w-tw+1}이므로 ({h-th+1}, {w-tw+1})입니다.",params={"h":h,"w":w,"th":th,"tw":tw})

@gen("a04-g02", unit="a4f", level=2, tags=["app.a4f"], ref=["응용 4차시 노트북 07 [8]"], facts=["FA04-f"], basis="lecture-formula", step="a4f/4")
def flow_endpoint(r):
    x, y = r.int(10, 60), r.int(10, 60)
    dx, dy, scale = r.int(-6, 6), r.int(-6, 6), r.pick([1, 2, 3])
    return blank(stem=f"시작 위치 (x, y)=({x}, {y})에서 flow[y, x]=(dx, dy)=({dx}, {dy})입니다. 화살표 표시 배율이 {scale}일 때 끝점의 x는 ____ 입니다.",blanks=[{"answer":[str(x+scale*dx)],"mode":"number"}],explain=f"시작 x에 가로 변위와 표시 배율의 곱을 더합니다. {x}+({dx})×{scale}={x+scale*dx}입니다. 원래 변위는 바뀌지 않습니다.",params={"x":x,"y":y,"dx":dx,"dy":dy,"scale":scale})

template_shape.gen_spec.meta.update(template_revision="template-map-1", author_difficulty=2, display_params=["h","w","th","tw"])
flow_endpoint.gen_spec.meta.update(template_revision="flow-endpoint-1", author_difficulty=2, display_params=["x","y","dx","dy","scale"])
