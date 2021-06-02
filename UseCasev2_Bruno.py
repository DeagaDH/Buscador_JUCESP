from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import numpy as np
import cv2
import sys
import time

def busca_empresa(param_busca,selenium_timeout=2,espera_captcha=3):
    """
    Realiza uma busca por empresas em 'http://www.institucional.jucesp.sp.gov.br/'
    
    Argumentos:

    param_busca      -- Nome ou NIRE da empresa a ser pesquisada.

    selenium_timeout -- Valor utilizado como implicitly_wait do Selenium para aguardar carregamento 
                        de elementos da página, em segundos. Após este tempo, retorna exceção de
                        elemento não encontrado (NoSuchElementException). Pode ser aumentado para
                        evitar este erro em caso de conexão lenta.

    espera_captcha   -- Tempo para esperar o carregamento total da imagem do CAPTCHA da página, em 
                        segundos. Se for muito curto, a função de avaliar CAPTCHA pode não funcionar
                        corretamente. Usar valores maiores em conexões lentas para evitar problemas.

    Caso param_busca seja NIRE de uma empresa, retorna um dicionário com dados da empresa (ver função 
    coleta_nire)

    Caso param_busca seja um nome de empresa para busca, retorna uma lista de dicionários, contendo
    NIRE, nome e município das empresas encontradas (ver função coleta_nome)
    """

    # Configurar navegador
    chrome_options = Options()
    chrome_options.add_argument("--headless") #Modo headless
    chrome_options.add_argument("--window-size=1920x1080") #Tamanho grande para facilitar screenshot do CAPTCHA
    chrome_options.add_argument("--log-level=3")  #Não exibir muitos logs
    driver = webdriver.Chrome(ChromeDriverManager().install(),options=chrome_options)
    
    # Configurar tempo de espera implícito do Selenium, em segundos.
    driver.implicitly_wait(selenium_timeout)
    
    # Abrir página inicial (conforme instrções em provaUseCasev2.pdf)
    driver.get('http://www.institucional.jucesp.sp.gov.br/')

    # Clicar no botão de pesquisa e ir para página de pesquisa
    driver.find_element_by_link_text('Pesquisa de empresas no banco de dados da Junta Comercial do Estado de São Paulo.').click()

    # Abrir página de pesquisa e localizar o campo de busca
    id_busca = 'ctl00_cphContent_frmBuscaSimples_txtPalavraChave' #ID do campo de pesquisa
    busca = driver.find_element_by_id(id_busca)

    # Efetuar busca por param_busca
    busca.send_keys(param_busca)
    busca.send_keys(Keys.ENTER)

    # Avaliar captcha manualmente (solução solicitada ao usuário)
    avalia_captcha(driver,espera_captcha) #Função definida abaixo

    # Checar se o parâmetro de busca é nome ou NIRE. Se for apenas números e com 11 dígitos, é um NIRE.
    if param_busca.isdecimal() and len(param_busca) == 11:
        resultado = coleta_nire(driver) # Definida abaixo
    else:
        resultado = coleta_nome(driver) # Definida abaixo

    # Fechar Browser
    driver.quit()

    # Retornar resultado da busca
    return resultado

def avalia_captcha(driver,espera_captcha=3):
    """
    Captura a imagem do CAPTCHA da página, exibe na tela e solicita
    a solução ao usuário. 
    
    Argumentos:

    driver         -- Driver do Selenium que está sendo utilizado para navegar a página.

    espera_captcha --  Tempo para esperar o carregamento total da imagem do CAPTCHA da página, em 
                       segundos. Se for muito curto, a função de avaliar CAPTCHA pode não funcionar
                       corretamente. Usar valores maiores em conexões lentas para evitar problemas. 
    
    Retorna o valor fornecido pelo usuário.
    """

    #XPATH da imagem do captcha
    xpath_captcha = '//*[@id="formBuscaAvancada"]/table/tbody/tr[1]/td/div/div[1]/img'

    # Nome do campo para se digitar o captcha
    nome_campo_captcha = 'ctl00$cphContent$gdvResultadoBusca$CaptchaControl1' 
    
    # Contador de tentativas do CAPTCHA. Encerrar se superar máximo
    tentativas = 0
    max_tentativas = 5

    #Aguardar carregamento inicial da página
    time.sleep(espera_captcha)

    # Pedir ao usuário que digite o captcha até acertar
    while tentativas < max_tentativas:
        # Tentar encontrar o elemento de captcha (figura + campo para digitar)
        try:
            captcha = driver.find_element_by_xpath(xpath_captcha)
            campo_captcha = driver.find_element_by_name(nome_campo_captcha)

        except NoSuchElementException:
            # Se o CAPTCHA sumir, foi resolvido. Sair da função de solução de CAPTCHA.
            return

        # Tirar screenshot da página para mostrar o CAPTCHA ao usuário
        screenshot = driver.get_screenshot_as_png()
        screenshot = np.frombuffer(screenshot, np.uint8) # Transformar em array numpy para depois decodificar

        # Localização e tamanho do CAPTCHA, para recortar o screenshot da página
        localizacao = captcha.location
        tamanho = captcha.size
        
        # Coordenadas dos quatro cantos do CAPTCHA
        x0=localizacao['x']
        xf=x0 + tamanho['width']
        y0=localizacao['y']
        yf=y0 + tamanho['height']

        # Ler screenshot e cortar para mostrar somente o captcha
        img_captcha = cv2.imdecode(screenshot, cv2.IMREAD_COLOR)
        crop_captcha = img_captcha[y0:yf,x0:xf] # Cortar 

        # Exibir CAPTCHA e soliticar input ao usuário
        crop_captcha = cv2.resize(crop_captcha, (0, 0), fx=1.5, fy=1.5) #Ampliar
        cv2.imshow('CAPTCHA',crop_captcha)
        cv2.waitKey(1) # Necessário para imshow não travar
        captcha = input('Digite o captcha: ')
        cv2.destroyAllWindows() # Fechar janela de imagem

        # Enviar o captcha no campo correto 
        campo_captcha.send_keys(captcha)
        campo_captcha.send_keys(Keys.ENTER)

        #Incrementar contador de tentativas
        tentativas += 1

        #Aguardar carregamento da página
        time.sleep(espera_captcha)

    # Encerrar processo se o máximo de tentativas for atingido
    print('Número máximo de tentativas do CAPTCHA atingido. Encerrando...')
    driver.quit()
    sys.exit(1)

def coleta_nire(driver):
    """
    Coletar informações quando o NIRE da empresa é fornecido como parâmetro de busca.
    Neste caso, é retornada uma página com diversos dados da empresa.

    Argumentos:

    driver -- Driver do Selenium que está sendo utilizado para navegar a página.

    Esta função retorna um dicionário os dados da empresa, sendo suas chaves:
    'nome', 'tipo de empresa', 'início de atividade', 'cnpj', 'nire, 'data da constituição',
    'inscrição estadual', 'objeto', 'capital', 'logradouro', 'número', 'bairro', 'município', 
    'cep', 'uf'. 
    """

    # ID da divisão com dados da empresa
    id_div ='dados'

    # Verificar carregamento da divisão
    if not obteve_resultados(driver,id_div):
        return None # Se não há resultados, retornar None.

    # Parsear com BeautifulSoup
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    div_dados = soup.find('div',{'id':id_div})

    # Dicionário vazio para resultados
    dicionario_res = {}

    # Adicionar informações ao dicionário
    dicionario_res['nome'] = div_dados.find('span',{'id': 'ctl00_cphContent_frmPreVisualiza_lblEmpresa'}).get_text()
    dicionario_res['tipo de empresa'] = div_dados.find('span',{'id': 'ctl00_cphContent_frmPreVisualiza_lblDetalhes'}).get_text()
    dicionario_res['início de atividade'] = div_dados.find('span',{'id': 'ctl00_cphContent_frmPreVisualiza_lblAtividade'}).get_text()
    dicionario_res['cnpj'] = div_dados.find('span',{'id': 'ctl00_cphContent_frmPreVisualiza_lblCnpj'}).get_text()
    dicionario_res['nire'] = div_dados.find('span',{'id': 'ctl00_cphContent_frmPreVisualiza_lblNire'}).get_text()
    dicionario_res['data da constituição'] = div_dados.find('span',{'id': 'ctl00_cphContent_frmPreVisualiza_lblConstituicao'}).get_text()
    dicionario_res['inscrição estadual'] = div_dados.find('span',{'id': 'ctl00_cphContent_frmPreVisualiza_lblInscricao'}).get_text()
    dicionario_res['objeto'] = div_dados.find('span',{'id': 'ctl00_cphContent_frmPreVisualiza_lblObjeto'}).get_text(separator='. ') #Tratar tags <br> que aparecem neste campo
    dicionario_res['capital'] = div_dados.find('span',{'id': 'ctl00_cphContent_frmPreVisualiza_lblCapital'}).get_text()
    dicionario_res['logradouro'] = div_dados.find('span',{'id': 'ctl00_cphContent_frmPreVisualiza_lblLogradouro'}).get_text()
    dicionario_res['número'] = div_dados.find('span',{'id': 'ctl00_cphContent_frmPreVisualiza_lblNumero'}).get_text()
    dicionario_res['bairro'] = div_dados.find('span',{'id': 'ctl00_cphContent_frmPreVisualiza_lblBairro'}).get_text()
    dicionario_res['complemento'] = div_dados.find('span',{'id': 'ctl00_cphContent_frmPreVisualiza_lblComplemento'}).get_text()
    dicionario_res['município'] = div_dados.find('span',{'id': 'ctl00_cphContent_frmPreVisualiza_lblMunicipio'}).get_text()
    dicionario_res['cep'] = div_dados.find('span',{'id': 'ctl00_cphContent_frmPreVisualiza_lblCep'}).get_text()
    dicionario_res['uf'] = div_dados.find('span',{'id': 'ctl00_cphContent_frmPreVisualiza_lblUf'}).get_text()

    # Tratamento especial para o campo 'capital'. Costuma ter diversos espaços em branco.
    dicionario_res['capital'] = ' '.join(dicionario_res['capital'].split())

    return dicionario_res

def coleta_nome(driver):
    """
    Coletar informações quando o NOME da empresa é fornecido como parâmetro de busca.
    Neste caso, a página retorna uma tabela contendo NIRE, nome e Município das
    empresas encontradas.

    Argumentos:

    driver -- Driver do Selenium que está sendo utilizado para navegar a página.

    A função retorna uma lista de dicionários, sendo cada item da lista correspondente a
    uma linha da tabela. As chaves de cada dicionário são: 'NIRE', 'Empresa', 'Município'.

    Apenas itens da primeira página de resultdos são considerados, conforme solicitado
    nas instruções (provaUseCasev2.pdf)
    """
    
    # ID da tabela de resultados
    id_tabela ='ctl00_cphContent_gdvResultadoBusca_gdvContent'
    
    # Verificar carregamento da tabela
    if not obteve_resultados(driver,id_tabela):
        return None # Se não há resultados, retornar None.

    # Parsear com BeautifulSoup
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    tabela = soup.find('table',{'id':id_tabela})

    #Lista vazia para adicionar dicionários
    lista_resultados = []

    # Percorrer todas as linhas da tabela
    for linha in tabela.find_all('tr')[1:]: #Pular primeira linha (cabeçalho)
        
        #Dicionário vazio em cada linha
        dicionario = {}

        #Obter colunas da tabela
        colunas = linha.find_all('td')

        # Segunda coluna: Empresa (Fazer primeiro para resultado ficar igual ao desejado)
        empresa = colunas[1].get_text().replace('\n','')
        dicionario['Empresa'] = empresa

        # Primeira coluna: NIRE (Fazer segundo para resultado ficar igual ao desejado)
        nire = colunas[0].find('a').get_text()
        dicionario['NIRE'] = nire        

        # Terceira coluna: Município
        municipio = colunas[2].get_text().replace('\xa0','') #Deixar campos vazios em branco
        dicionario['Município'] = municipio

        # Adicionar à lista de resultados
        lista_resultados.append(dicionario)

    return lista_resultados

def obteve_resultados(driver, id_desejado):
    """
    Verifica se a busca teve êxito.

    Argumentos:

    driver      -- Driver do Selenium que está sendo utilizado para navegar a página.

    id_desejado -- ID do objeto desejado (tabela de resultados, página de resultados, etc) que
                   aparece uma busca com êxito.

    A verificação checa se o objeto com id 'id_desejado' foi carregado.
    Caso não seja, verifica se o ID de busca 0 resultados apareceu.
    """
    

    # Veficar se o objeto com id_desejado apareceu na página.
    try:
        # Verificar se foi encontrado
        driver.find_element_by_id(id_desejado)

        return True
    except:
        # ID desejado não encontrado! Talvez a busca não tenha encontrado resultados.

        # Verificar se apareceu a mensagem de busca sem resultados       
        id_erro = 'ctl00_cphContent_gdvResultadoBusca_qtpGridview_lblMessage' #ID da mensagem de erro de 0 resultados encontrados  
        driver.find_element_by_id(id_erro) #Dará erro de timeout em caso de perda de conexão
        print('A busca não obteve resultados. Verifique o nome ou NIRE fornecido e tente novamente.')
        return False 

if __name__ == '__main__':
    # Solicitar parâmetro de busca ao usuário
    param_busca = input('Digite o nome ou NIRE a pesquisar: ')

    # Efetuar busca por empresa
    resultado = busca_empresa(param_busca)
        
    # Imprimir para verificação, a fim do projeto
    # Acredito que, na prática, o resultado da busca seria agregado a um banco de dados
    # ou utilizado de alguma outra maneira
    if resultado:
        print("Resultado da busca:")
        print(resultado)