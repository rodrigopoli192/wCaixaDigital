import re

import fdb
import pymssql

from caixa_nfse.core.models import ConexaoExterna


class SQLExecutor:
    @staticmethod
    def extract_variables(sql):
        """
        Extracts variables from SQL query in the format @VAR_NAME.
        Returns a list of unique variable names.
        """
        pattern = r"@(\w+)"
        variables = re.findall(pattern, sql)
        return list(set(variables))

    @staticmethod
    def get_connection(conexao: ConexaoExterna):
        """
        Establishes a connection based on ConexaoExterna settings.
        """
        if conexao.tipo_conexao == ConexaoExterna.TipoConexao.FIREBIRD:
            return fdb.connect(
                host=conexao.host,
                port=conexao.porta,
                database=conexao.database,
                user=conexao.usuario,
                password=conexao.senha,
                charset=conexao.charset or "WIN1252",
            )
        elif conexao.tipo_conexao == ConexaoExterna.TipoConexao.MSSQL:
            server = conexao.host
            # if conexao.instancia:
            #     server = f"{conexao.host}\\{conexao.instancia}"

            return pymssql.connect(
                server=server,
                port=conexao.porta,
                user=conexao.usuario,
                password=conexao.senha,
                database=conexao.database,
                timeout=10,
            )
        else:
            raise ValueError(f"Tipo de conexão não suportado: {conexao.tipo_conexao}")

    @staticmethod
    def execute_routine(conexao: ConexaoExterna, sql: str, params: dict = None):
        """
        Executes the SQL routine with the provided parameters.
        Returns a tuple (headers, rows, logs).
        """
        import datetime

        logs = []

        def log(msg, type="info"):
            now = datetime.datetime.now().strftime("%H:%M:%S")
            logs.append({"time": now, "msg": msg, "type": type})

        if params is None:
            params = {}

        log(f"Iniciando execução da rotina. Parâmetros recebidos: {list(params.keys())}")

        # Basic SQL Injection prevention for the specific @VAR syntax
        processed_sql = sql
        try:
            # Sort by length desc to prioritize longer variable names (extra safety)
            sorted_params = sorted(params.items(), key=lambda x: len(x[0]), reverse=True)

            for key, value in sorted_params:
                if not re.match(r"^\w+$", key):
                    raise ValueError(f"Nome de variável inválido: {key}")

                val_str = str(value).strip()

                # Date Handling: Convert to YYYYMMDD (Safe for MSSQL)
                if re.match(r"^\d{4}-\d{2}-\d{2}$", val_str):
                    # YYYY-MM-DD -> YYYYMMDD
                    val_str = val_str.replace("-", "")
                    log(f"Formatando data (ISO) para {val_str}...", "info")
                elif re.match(r"^\d{2}/\d{2}/\d{4}$", val_str):
                    # DD/MM/YYYY -> YYYYMMDD
                    day, month, year = val_str.split("/")
                    val_str = f"{year}{month}{day}"
                    log(f"Formatando data (BR) para {val_str}...", "info")

                clean_value = val_str.replace("'", "''")

                # Use regex to avoid partial matches (e.g. replacing @DATA in @DATA_FIM)
                # Matches @KEY not followed by a word character
                pattern = re.compile(rf"@{re.escape(key)}(?!\w)", re.IGNORECASE)
                processed_sql = pattern.sub(f"'{clean_value}'", processed_sql)

                log(f"Substituindo variável @{key}...", "info")

            log("SQL processado com sucesso.", "success")

        except Exception as e:
            log(f"Erro no processamento do SQL: {str(e)}", "error")
            return [], [], logs

        conn = None
        try:
            log(
                f"Conectando ao banco {conexao.get_tipo_conexao_display()} | "
                f"Host: {conexao.host}:{conexao.porta} | "
                f"DB: {conexao.database} | "
                f"User: {conexao.usuario}",
                "info",
            )
            conn = SQLExecutor.get_connection(conexao)
            cursor = conn.cursor()
            log("Conexão estabelecida.", "success")

            # Log formatted SQL before execution for debugging
            log(f"SQL Final: {processed_sql}", "info")

            log("Executando query...", "info")
            cursor.execute(processed_sql)

            # Fetch headers
            if cursor.description:
                headers = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                log(f"Query executada. {len(rows)} registros retornados.", "success")

                # Add sanitized SQL to log for debugging (be careful with sensitive data)
                log(
                    f"SQL Final: {processed_sql[:200]}..."
                    if len(processed_sql) > 200
                    else f"SQL Final: {processed_sql}",
                    "info",
                )

                return headers, rows, logs
            else:
                log("Query executada. Nenhum resultado retornado.", "warning")
                return [], [], logs

        except Exception as e:
            log(f"Erro na execução da query: {str(e)}", "error")
            return [], [], logs
        finally:
            if conn:
                conn.close()
                log("Conexão fechada.", "info")
