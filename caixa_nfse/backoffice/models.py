from django.db import models


class Sistema(models.Model):
    """
    Representa um sistema externo para o qual rotinas SQL são definidas.
    """

    nome = models.CharField(max_length=100)
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sistema"
        verbose_name_plural = "Sistemas"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Rotina(models.Model):
    """
    Representa uma rotina SQL associada a um sistema.
    """

    sistema = models.ForeignKey(Sistema, related_name="rotinas", on_delete=models.CASCADE)
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True, verbose_name="Descrição")
    sql_content = models.TextField(verbose_name="Conteúdo SQL")
    sql_content_extra = models.TextField(
        blank=True, null=True, verbose_name="Conteúdo SQL Adicional (Opcional)"
    )
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Rotina"
        verbose_name_plural = "Rotinas"
        ordering = ["sistema", "nome"]

    def __str__(self):
        return f"{self.sistema.nome} - {self.nome}"

    def extrair_variaveis(self):
        """Extract @VARIABLE names from SQL content. Returns sorted unique list."""
        import re

        # System-managed vars (injected automatically, never shown to user)
        SYSTEM_VARS = {"SERVICOANDAMENTO"}

        sql = self.sql_content or ""
        if self.sql_content_extra:
            sql += "\n" + self.sql_content_extra
        # Match @WORD_CHARS not inside quotes
        variaveis = set(re.findall(r"@(\w+)", sql, re.IGNORECASE))
        # Remove SQL Server built-in variables (@@IDENTITY, @@ROWCOUNT, etc.)
        variaveis = {v for v in variaveis if not v.startswith("@")}
        # Remove system-managed vars
        variaveis -= SYSTEM_VARS
        return sorted(variaveis)


class MapeamentoColunaRotina(models.Model):
    """
    Mapeia colunas retornadas por uma rotina SQL para campos do MovimentoImportado.
    Configurável pelo admin no backoffice.
    """

    CAMPOS_DESTINO_CHOICES = [
        ("protocolo", "Protocolo"),
        ("status_item", "Status"),
        ("quantidade", "Quantidade"),
        ("valor", "Valor Principal"),
        ("descricao", "Descrição"),
        ("cliente_nome", "Nome do Apresentante"),
        ("emolumento", "Emolumento"),
        ("taxa_judiciaria", "Taxa Judiciária"),
        ("iss", "ISS"),
        ("fundesp", "FUNDESP"),
        ("funesp", "FUNESP"),
        ("estado", "Estado"),
        ("fesemps", "FESEMPS"),
        ("funemp", "FUNEMP"),
        ("funcomp", "FUNCOMP"),
        ("fepadsaj", "FEPADSAJ"),
        ("funproge", "FUNPROGE"),
        ("fundepeg", "FUNDEPEG"),
        ("fundaf", "FUNDAF"),
        ("femal", "FEMAL"),
        ("fecad", "FECAD"),
    ]

    rotina = models.ForeignKey(Rotina, related_name="mapeamentos", on_delete=models.CASCADE)
    coluna_sql = models.CharField(
        "coluna SQL",
        max_length=100,
        help_text="Nome exato da coluna retornada pela query SQL",
    )
    campo_destino = models.CharField(
        "campo destino",
        max_length=50,
        choices=CAMPOS_DESTINO_CHOICES,
    )

    class Meta:
        verbose_name = "Mapeamento de Coluna"
        verbose_name_plural = "Mapeamentos de Colunas"
        unique_together = ["rotina", "campo_destino"]
        ordering = ["rotina", "campo_destino"]

    def __str__(self):
        return f"{self.coluna_sql} → {self.get_campo_destino_display()}"
