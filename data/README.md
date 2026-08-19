# TPC-H 数据生成与导入

本目录提供建表 DDL，不包含 SF=1 原始 `.tbl` 文件（约 1GB，不适合放进仓库）。下列命令均在**项目根目录**执行。

| 文件 | 用途 |
| ---- | ---- |
| `schema.sql` | PostgreSQL 建表 |
| `schema_ymatrix.sql` | MatrixDB / Greenplum 建表（含 `DISTRIBUTED BY`） |

## 1. 启动 PostgreSQL

先复制环境变量并填写密码：

```bash
copy .env.example .env
```

```bash
docker compose up -d
```

确认容器就绪：

```bash
docker exec -it tpch-postgres psql -U tpch -d tpch -c "SELECT version();"
```

电脑重启后若容器是 `Exited`，用 `docker start tpch-postgres`，不要重新 `docker compose up` 造第二个库。

## 2. 建表

```bash
docker exec -i tpch-postgres psql -U tpch -d tpch < data/schema.sql
```

Windows PowerShell：

```powershell
Get-Content data\schema.sql -Raw | docker exec -i tpch-postgres psql -U tpch -d tpch
```

## 3. 生成 TPC-H SF=1 数据

使用官方 `dbgen`：

```bash
# 编译后生成 8 张表的 .tbl 文件
./dbgen -s 1
```

将生成的 `nation.tbl`、`region.tbl`、`part.tbl`、`supplier.tbl`、`partsupp.tbl`、`customer.tbl`、`orders.tbl`、`lineitem.tbl` 拷贝到 `data/tbl/`。

## 4. 导入

dbgen 默认以 `|` 结尾。导入示例：

```sql
COPY nation FROM '/path/nation.tbl' WITH (FORMAT csv, DELIMITER '|');
```

若文件在宿主机，可用 `\copy`：

```bash
docker exec -i tpch-postgres psql -U tpch -d tpch -c "\copy nation FROM STDIN WITH (FORMAT csv, DELIMITER '|')" < data/tbl/nation.tbl
```

对 8 张表重复执行。`lineitem` 最大，SF=1 导入可能需要数分钟。

导入后如需与本次报告对齐，建立：

```sql
CREATE INDEX IF NOT EXISTS idx_lineitem_combo
  ON lineitem (l_partkey, l_suppkey, l_shipdate);
```

本次 PostgreSQL 补测与双库对比两边都有该索引。

## 5. 校验

```sql
SELECT 'nation' AS t, COUNT(*) FROM nation
UNION ALL SELECT 'region', COUNT(*) FROM region
UNION ALL SELECT 'part', COUNT(*) FROM part
UNION ALL SELECT 'supplier', COUNT(*) FROM supplier
UNION ALL SELECT 'partsupp', COUNT(*) FROM partsupp
UNION ALL SELECT 'customer', COUNT(*) FROM customer
UNION ALL SELECT 'orders', COUNT(*) FROM orders
UNION ALL SELECT 'lineitem', COUNT(*) FROM lineitem;
```

SF=1 参考行数：nation 25、region 5、part 200000、supplier 10000、partsupp 800000、customer 150000、orders 1500000、lineitem 6001215。

## 6. 导入到 YMatrix（双库对比用）

社区版没有 Windows 安装包。本次对比用的是 Docker 容器 `mxdemo`（镜像 `matrixdb/centos7_demo`，**MatrixDB 4.8.12-community**，不是 5.2.1）。宿主机端口 **5433** 映射到容器 5432。

若容器已经初始化过：

```powershell
docker start mxdemo
```

不要再 `docker run --name mxdemo`（名字冲突）。把 `config.compare.example.yaml` 复制为 `config.compare.yaml` 并填写两边密码后：

```powershell
python scripts\copy_tpch_to_ymatrix.py --config config.compare.yaml
```

会执行：创建 `tpch` 库、应用 `data/schema_ymatrix.sql`、COPY 8 张表、核对行数、创建 `idx_lineitem_combo`。

然后再：

```powershell
python main.py --config config.compare.yaml
```

YMatrix 的 `session_params` 不要设置 `jit`（该 GUC 可能不存在，`SET` 失败会导致 22 条全部失败）。
