# 观澜档案 · 抽样复核预算

对有限档案总体计算精确检出概率，在预算与风险层容量约束下分配整数配额，保存固定seed抽出的具体文档编号。面向观澜档案数字化验收组15人，全部为模拟批次。

## 场景

原流程用 `guanlan_acceptance_202611.csv` 在Excel统一抽10%。三个痛点是小批次无放回概率误算、风险层样本分配缺少依据、临时加样使预算超支。上游为数字化批次底册和历史预估差错率；本项目替代抽样设计、预算复核和编号留档；下游为人工复核员逐份检查、验收负责人审核。

六实体贯穿数据库、Python Model/Schema/Service/Controller/Route和Vue API/Store/页面：ArchiveLot（批次）、SamplingPlan（计划）、AllocationRun（可行性与配额）、SampleDraw（具体抽样）、ReviewDecision（人工复核）、CheckItem（逐份检查结果）、Report（批准快照）。风险层为批次属性，同一层内合并所选批次作等概率抽样。

## 逐份复核与批准闸门

说明文字不能代替逐份检查。每个抽样清单建立复核单后，必须对清单内**每一份**档案登记 `qualified`（合格）或 `error`（差错），漏检或冲突未清的清单不能批准：

- **离线结果合并**：按 `source`（复核员/离线设备标识）批量报送，支持粘贴 `文档编号,合格|差错` 文本导入。同一 `(复核单, 文档, 来源)` 重复报送幂等不增计，仅以最新报送覆盖同来源结论与备注。
- **矛盾结论保留冲突**：不同来源对同一文档给出相反结论时，全部条目保留并标记冲突，进入管理员裁决队列；冲突文档不计入合格也不计入差错。
- **管理员裁决**：仅 admin 可裁决，裁决写入 `adjudication` 来源条目，被否定的原始条目标记 `superseded` 留痕，可重新裁决。
- **批准闸门**：`POST /reviews/{id}/approve` 校验漏检数与未裁决冲突数均为 0，否则 409；批准后结果锁定，拒绝再登记或再裁决。
- **封存**：生成报告即封存，复核单转为 `sealed`，逐份结论、来源、裁决留痕与统计口径写入 `reviews.sealed_evidence` 与 `reports.snapshot`，CSV 含逐份证据段。

## 启动

```sh
cp .env.example .env
docker compose up -d --build --wait
docker compose exec -T backend python -m scripts.seed_demo
```

前端 http://localhost:18217 ，API文档 http://localhost:19217/docs ，MySQL宿主端口17717。Nginx将 `/api/` 去前缀转发到Python；Vite开发代理相同。`/health`实际检查数据库和Redis。

五服务恰好为frontend/backend/worker/db/redis，全部有健康检查，数据库/Redis/worker共享产物分别使用具名卷。后台通过Redis队列执行，不在浏览器计算配额。清理演示数据 `docker compose down -v --remove-orphans`；保留数据时去掉 `-v`。

## 技术与结构

| 层 | 版本/实现 |
|---|---|
| 前端 | Vue3.5.13、TypeScript5.7、Vite6、Vue Router4 |
| 后端 | Python3.12、FastAPI0.115.6、SQLAlchemy2 |
| 存储 | MySQL8.4 LTS、Redis7.4 |
| 算法 | Python整数math.comb、Fraction目标比较、Decimal差错数向上取整、确定性Neyman分配 |
| 抽样 | Python Random(seed).sample，无放回，清单保存数据库 |
| 网关 | Nginx1.28、SPA回落及API代理 |

- `backend/src/models,schemas,services,controllers,routes`：按六实体分层。
- `services/hypergeometric.py`：漏检概率/最小样本量；`neyman.py`：整数配额；`allocation.py`：风险层汇总/可行性；`draw_service.py`：具体文档编号；`confidence.py`：实测差错的有限总体单侧95%置信上界；`review_service.py`：离线合并、去重、冲突裁决与批准闸门。
- `models/check.py`（CheckItem）：逐份合格/差错登记，唯一键 `(review_id, document_id, source)` 保证同来源幂等；`reviews.sealed_evidence` 保存封存证据。
- `config,utils,middlewares`：环境变量、数据库、认证、队列、审计及统一错误。
- `backend/scripts/seed_demo.py`：自然键幂等；`migrations/001_schema.sql`：新库基线说明，以SQLAlchemy元数据建表。
- `frontend/src/api,stores,types,constants,hooks,pages,router`：完整业务入口；共享AllocationTable、QuotaBars、ManifestTable分别跨总览/配额/归档复用。
- 测试与截图在批次外层 `test-artifacts/gb-2208`，不放在源码内。

本地开发：安装backend/requirements.txt，在backend目录设置可用DATABASE_URL/REDIS_URL后运行 `uvicorn src.main:app --reload`；另起 `python -m src.worker`。前端 `npm install && npm run dev`，构建 `npm run build` 同时执行vue-tsc。

配置变量COMPOSE_PROJECT_NAME、FRONTEND_PORT、BACKEND_PORT、DB_PORT、JWT_SECRET、SEED_DEMO；DATABASE_URL/REDIS_URL由Compose内部提供。`.env`不进源码包。演示口令与密钥用于本地模拟，部署使用独立配置。

## 账号与权限

统一演示密码 `ArchiveDemo2026!`。PBKDF2-SHA256带独立salt口令摘要，JWT八小时有效。

| 账号/角色 | 主要动作 | 权限 |
|---|---|---|
| admin@sample.demo / admin | 核准复核、冲突裁决、归档、审计 | 全部分析写入、裁决与批准封存 |
| analyst@sample.demo / analyst | 批次、计划、计算、清单、逐份登记与离线合并 | 不能裁决、批准或归档 |
| viewer@sample.demo / viewer | 阅读和下载已批准清单 | 所有写入403 |

未认证401；错误角色403；不可行运行生成抽样409；未批准复核生成报告409；漏检或冲突未清批准409；已封存复核再登记409；清单外文档报送422。同一运行重复生成清单返回原清单，同一批准复核重复归档返回原快照。

共享枚举：Role/RunStatus/Stratum在 `backend/src/constants/enums.py`；前端roles/runStatuses/strata及strataLabels在 `frontend/src/constants/enums.ts`；Role类型见types/domain.ts。运行状态包括queued、running、completed、infeasible、failed；复核状态submitted（待复核）、approved（已批准锁定）、sealed（已封存证据）。检查条目状态active（有效）、superseded（裁决后被否定留痕）。

## 统计口径

### 复核后的实测差错置信上界

批准报告**不沿用抽样设计阶段的预估差错率/假设 D**，仅依据逐份实检结果。按风险层汇总层总体 N、实检份数 n、实测差错数 d，对总体差错总量 D 求 95% 单侧置信上界 U（Clopper–Pearson 型超几何口径）：

`U = min{ D : P_{N,D,n}(X <= d) <= 0.05 }`，其中 `P(X=k)=C(D,k)C(N−D,n−k)/C(N,n)`。

- 整数二分求解，组合数用任意精度整数、Fraction 交叉相乘比较，无浮点相消。
- **零差错照算**：d=0 时 U 为满足 `C(N−U,n)/C(N,n) <= 0.05` 的最小 U，不报零。
- 全检 n=N 时 U=d（总体差错数即观测值）；n=0 时无样本信息，U=N。
- 边界例：N=100、n=20、d=0 时 U=13（P(X=0|D=13)≈0.0443，D=12 时≈0.0574）；大总体小抽样比下与二项 CP 上界吻合。
- 设计阶段的假设 D、检出率仅作留档列，报告中明确标注 `design_only`，不参与实测结论。

### 风险层与假设差错数（抽样设计阶段）

每批记录文档总数N_lot、预估差错率p_lot、风险层及唯一文档前缀。文档编号为 `PREFIX-00001` 起连续序号。本项目不读取真实档案内容，也没有隐藏的真实差错标签。

**检出目标按风险层判断，不承诺每个批次分别达标。** 同层合并所选批次，N=sum N_lot，假设D=sum ceil(N_lot×p_lot)。向上取整使用Decimal(str(p))，避免100×0.07因浮点误差被错误向上取8。预估p不等于实测率；结果只在该固定D假设和层内等概率抽样下成立。

### 精确无放回检出概率

抽n份而一份差错也没发现的概率：

`P(miss)=C(N−D,n)/C(N,n)`，若n>N−D则为0；检出率=1−P(miss)。

组合数使用Python任意精度整数。最小样本量通过整数二分求解，目标以Fraction(str(target))表示，并对组合数作整数交叉相乘比较，避免边界处的浮点相消；展示概率最后才转浮点；界面仅在D>0且n>N−D的guaranteed标记为真时显示100%；其余高概率即使1−miss浮点舍入为1也显示“>99.99%”。CSV同时保存漏检率与guaranteed_detection，明确是否保证命中。target=1时直接采用保证命中的N−D+1，不能因为浮点显示1就宣称100%。D=0且目标>0时不可达；target=0时最小样本为0。

例N=10、D=2：n=7检出14/15≈93.3333%，n=8检出44/45≈97.7778%，因此95%目标最小为8，而100%需要9。

### Neyman整数配额

层内加权预估率p_h=sum(N_lot×p_lot)/N_h，权重w_h=N_h√(p_h(1−p_h))。先对各风险层求精确最低样本L_h：若预算B<ΣL_h、B>ΣN_h、或任一非零目标层D=0，运行状态为infeasible，保留原因，**不生成文档抽样**。

可行时求q_h=clip(λw_h,L_h,N_h)，调整λ满足总预算；连续配额向下取整后按最大余数分配，平局按风险层英文键固定排序。正方差层满容量后仍有预算，才对零方差层按固定层序轮流补足；此时Neyman解不唯一。最终严格Σn_h=B、L_h≤n_h≤N_h。

层内将所选批次文档拼为有限总体，用固定seed的 `random.sample` 不放回抽取。层和批次先按稳定键排序，重复运行同一计划得到相同文档与顺序。抽样清单一经保存不随刷新重抽；报告保存批准时清单及配额快照。

参数边界：每批1至5000份，计划最多30批，预算1至5000，目标0至1；非法风险层、重复批次选择、非法差错率拒绝。不存在批次422，名称/编号前缀冲突409。

## 模拟数据与工作日

12批、1800份档案：4风险层，每层100/150/200份三批；p分别0.01/0.03/0.06/0.12。默认计划预算480，目标95%，seed20261112。演示复核含两来源离线报送、一处矛盾结论及管理员裁决，批准后封存为已归档报告（482条检查记录）。

1. 09:00 核对 `guanlan_acceptance_202611.csv` 与12批底册的份数和前缀。
2. 09:04 复查预估差错率来源，确认四层口径而非逐批保证。
3. 09:08 设置95%目标、480份预算和固定seed。
4. 09:11 送入Redis队列，检查最低预算与可行性。
5. 09:16 查看Neyman整数配额、层容量及实际检出概率。
6. 09:20 打开具体文档清单，建立复核单，逐份登记合格/差错并按来源合并离线结果。
7. 09:25 管理员裁决矛盾结论；漏检或冲突未清时批准按钮禁用，清结后核准并锁定。
8. 09:30 生成归档快照封存逐份证据，下载含实测差错、95%单侧上界与逐份留痕的CSV。

种子按自然键检测，重复执行不新增或覆盖用户修改。密码、Token、原始请求正文不会写入审计。

## 已知差异

- 使用本机已有MySQL8.4 LTS，属于MySQL8家族；不是8.0镜像。
- Redis列表无worker崩溃租约及自动重投、无任务取消；可新建运行重试。
- 新数据库自动建表，没有存量数据库版本化迁移/回滚；实体列表最多200条，清单UI预览前80条匹配项，CSV保留全部。
- 档案为模拟编号；不上传真实文档、不执行OCR或判定实际差错。概率依赖固定D假设，不是验收质量保证。
- Google Fonts需联网，断网时回退字体。

MIT License。真实验收见批次 `test-artifacts/gb-2208/TESTING.md`。
