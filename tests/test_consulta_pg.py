"""Integração da consulta por ticket com o PostgreSQL 18 (pulado se indisponível)."""

from typing import Any

import psycopg
import pytest

from chat_ram.conhecimento.consulta import consultar_ticket
from chat_ram.conhecimento.dominio import StatusConsulta
from chat_ram.conhecimento.repositorio import PostgresTickets

NAO_EXISTENTE = "0000000000000000"


def test_consulta_o_primeiro_ticket_da_base(
    conexao_pg18: psycopg.Connection[Any],
) -> None:
    with conexao_pg18.cursor() as cursor:
        cursor.execute("SELECT tn FROM ticket ORDER BY id LIMIT 1")
        linha = cursor.fetchone()
    if linha is None:
        pytest.skip("base sem tickets")

    fonte = PostgresTickets(conexao_pg18)
    resultado = consultar_ticket(fonte, str(linha[0]))

    assert resultado.status == StatusConsulta.ENCONTRADO
    assert resultado.ticket is not None
    assert resultado.ticket.tn == str(linha[0])
    assert resultado.ticket.fila
    assert resultado.ticket.situacao
    datas = [artigo.data for artigo in resultado.ticket.artigos]
    assert datas == sorted(datas)


def test_numero_inexistente_nao_e_encontrado(
    conexao_pg18: psycopg.Connection[Any],
) -> None:
    fonte = PostgresTickets(conexao_pg18)

    resultado = consultar_ticket(fonte, NAO_EXISTENTE)

    assert resultado.status == StatusConsulta.NAO_ENCONTRADO
    assert resultado.ticket is None
