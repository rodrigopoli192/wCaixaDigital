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
    ativo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Rotina"
        verbose_name_plural = "Rotinas"
        ordering = ["sistema", "nome"]

    def __str__(self):
        return f"{self.sistema.nome} - {self.nome}"
